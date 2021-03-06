import numpy as np
import torch
from tqdm import tqdm

from models.util import weights_init, bn_momentum_adjust


def get_model(model_name: str, n_classes: int, use_rgb: bool):
    model_name = model_name.lower().replace(" ", "").replace("_", "")
    info_channel = 0
    if use_rgb:
        info_channel = 3
    if model_name == "pointnet":
        from models.pointnet.model import PointNet
        from models.pointnet.loss import Loss
        model = PointNet(n_classes, info_channel)
        criterion = Loss(mat_diff_loss_scale=0.001)  # TODO replace magic constant
    elif model_name in ["pointnet++ssg", "pointnet2ssg"]:
        from models.pointnet2.model import PointNet2SSG
        from models.pointnet2.loss import Loss
        model = PointNet2SSG(n_classes, info_channel)
        criterion = Loss()
    elif model_name == "dgcnn":
        from models.dgcnn.model import DGCNN
        from models.pointnet2.loss import Loss
        model = DGCNN(info_channel + 3, n_classes)
        criterion = Loss()  # TODO replace magic constant
    elif model_name in ["pointnet++msg", "pointnet2msg"]:
        from models.pointnet2.model import PointNet2MSG
        from models.pointnet2.loss import Loss
        model = PointNet2MSG(n_classes, info_channel)
        criterion = Loss()
    elif model_name in ["pointnet#", "pointnetsharp"]:
        from models.pointnetsharp.model import PointNet
        from models.pointnet2.loss import Loss
        model = PointNet(n_classes, info_channel)
        criterion = Loss()
    else:
        raise NotImplementedError(
            f"Chosen model ({model_name} is not available, must be in ('pointnet', 'pointnet++ssg', 'pointnet++msg')"
        )

    return model, criterion


class TestModel:
    '''
     Wrapper to hide the low-level pytorch calls
     '''

    def __init__(self, model_name, n_classes, logger, checkpoint_dir, use_rgb):
        # set hyperparameter
        # set visible devices (how many GPUs are used for training)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.n_classes = n_classes

        self.logger, self.checkpoint_dir = logger, checkpoint_dir

        # init model
        model, criterion = get_model(model_name, self.n_classes, use_rgb)

        # push to correct device
        self.model = model.to(self.device)
        self.criterion = criterion.to(self.device)

        # TODO this should be optional through parameters
        try:
            checkpoint = torch.load(str(self.checkpoint_dir) + '/best_model.pth')
            self.start_epoch = checkpoint['epoch']
            self.model.load_state_dict(checkpoint['model_state_dict'])
            self.logger.info('Use pretrain model')
        except:
            self.logger.info('No existing model, starting training from scratch...')
            self.start_epoch = 0
            self.model = model.apply(weights_init)

    def load_model(self, name):
        savepath = f"{str(self.checkpoint_dir)}/{name}.pth"
        self.logger.info('Load model from %s' % savepath)
        state = torch.load(savepath, map_location="cpu")
        self.model.load_state_dict(state["model_state_dict"])
        return state

    def eval(self, loader):
        '''Evaluate on all scenes'''
        num_batches = len(loader)
        total_correct = 0
        loss_sum = 0
        total_seen = 0
        class_distribution = np.zeros(self.n_classes)
        total_seen_class = np.zeros(self.n_classes)
        total_correct_class = np.zeros(self.n_classes)
        total_iou_deno_class = np.zeros(self.n_classes)
        predictions = [np.zeros((len(room), self.n_classes)) for room in loader.dataset.room_labels]
        n_pred = [np.zeros_like(room) for room in loader.dataset.room_labels]

        self.model.eval()
        with torch.no_grad():  # no gradient required
            for i, (points, target, point_idxs, room_idxs) in tqdm(enumerate(loader), total=len(loader), smoothing=0.9):
                # skip empty slices (no points)
                if points.shape[2] == 0:
                    num_batches -= 1  # since we skip a batch
                    continue
                points, target = points.to(self.device), target.to(self.device)
                bs = points.shape[0]  # should be 1

                # apply model
                seg_pred, trans_feat = self.model(points)

                # TODO there might be a faster way to do this
                for bi in range(bs):
                    point_idx, room_idx = point_idxs[bi], room_idxs[bi]
                    if len(point_idx) == 1:  # edge case if there is only one point in the sample
                        point_idx = [point_idx]
                    predictions[room_idx][point_idx] += seg_pred[bi].cpu().numpy()
                    n_pred[room_idx][point_idx] += 1

                loss = self.criterion(seg_pred.view(-1, self.n_classes), target.view(-1), trans_feat, None)
                loss_sum += loss

        # combine predictions
        predictions = [np.argmax(pred / n[:, None], 1) for pred, n in zip(predictions, n_pred)]

        room_labels = loader.dataset.room_labels
        # calculate eval scores
        for room_preds, room_labels in zip(predictions, room_labels):
            total_correct += np.sum((room_preds == room_labels))
            total_seen += len(room_preds)

            counts, _ = np.histogram(room_labels, range(self.n_classes + 1))
            class_distribution += counts
            for j in range(self.n_classes):
                total_seen_class[j] += np.sum((room_labels == j))
                total_correct_class[j] += np.sum((room_preds == j) & (room_labels == j))
                total_iou_deno_class[j] += np.sum(((room_preds == j) | (room_labels == j)))

        class_distribution = class_distribution / (np.sum(class_distribution) + 1e-6)
        mIoU = np.mean(np.array(total_correct_class) / (np.array(total_iou_deno_class) + 1e-6))
        acc = total_correct / total_seen
        class_acc = np.mean(np.array(total_correct_class) / (np.array(total_seen_class) + 1e-6))

        eval_loss = loss_sum / float(num_batches)
        return (
            eval_loss, mIoU, acc, class_acc, total_correct_class,
            total_iou_deno_class, class_distribution, predictions
        )


class TrainModel(TestModel):
    '''
    Wrapper to hide the low-level pytorch calls
    '''

    def __init__(self, model_name, optimizer_name, n_classes, lr, lr_decay, weight_decay,
                 step_size, class_weights, logger, checkpoint_dir, use_rgb):
        # set hyperparameter
        # set visible devices (how many GPUs are used for training)
        super().__init__(model_name, n_classes, logger, checkpoint_dir, use_rgb)
        self.class_weights = class_weights
        if self.class_weights is not None:  # is a tensor
            self.class_weights = self.class_weights.to(self.device)

        # init optimizer
        optimizer_name = optimizer_name.lower()
        if optimizer_name == 'adam':
            self.optimizer = torch.optim.AdamW(
                self.model.parameters(), lr=lr, betas=(0.9, 0.999), eps=1e-05, weight_decay=weight_decay
            )
        elif optimizer_name == "sgd":
            self.optimizer = torch.optim.SGD(self.model.parameters(), lr=lr, momentum=0.9)
        else:
            raise NotImplementedError(f"Only supports Adam and SGD for now, you selected: {self.optimizer}.")
        self.lr = lr
        self.lr_decay = lr_decay
        self.step_size = step_size

        # TODO this should be parameters not constants
        self.learning_rate_clip = 1e-5
        self.momentum_original = 0.1
        self.momentum_decay = 0.5
        self.momentum_decay_step = step_size

    def adjust_lr(self, epoch):
        lr = max(self.lr * (self.lr_decay ** (epoch // self.step_size)), self.learning_rate_clip)
        self.logger.info('Learning rate:%f' % lr)
        for param_group in self.optimizer.param_groups:
            param_group['lr'] = lr

    def adjust_bn_momentum(self, epoch):
        momentum = self.momentum_original * (self.momentum_decay ** (epoch // self.momentum_decay_step))
        if momentum < 0.01:
            momentum = 0.01
        self.logger.info('BN momentum updated to: %f' % momentum)
        self.model = self.model.apply(lambda x: bn_momentum_adjust(x, momentum))

    def load_model(self, name):
        state = super().load_model(name)
        self.optimizer.load_state_dict(state["optimizer_state_dict"])
        return state

    def save_model(self, epoch, mIoU, name="model"):
        savepath = f"{str(self.checkpoint_dir)}/{name}.pth"
        self.logger.info('Saving model to %s' % savepath)
        state = {
            'epoch': epoch,
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'miou': mIoU,
        }
        torch.save(state, savepath)

    def train(self, loader):
        '''Train on chopped scenes'''

        num_batches = len(loader)
        total_correct = 0
        total_seen = 0
        loss_sum = 0

        self.model.train()
        for points, target in tqdm(loader, total=num_batches, smoothing=0.9):
            points, target = points.to(self.device), target.to(self.device)
            bs = points.shape[0]
            self.optimizer.zero_grad()

            # apply model and make gradient step
            seg_pred, trans_feat = self.model(points)
            seg_pred = seg_pred.contiguous().view(-1, self.n_classes)
            batch_label = target.view(-1, 1)[:, 0].cpu().data.numpy()
            target = target.view(-1, 1)[:, 0]
            loss = self.criterion(seg_pred, target, trans_feat, self.class_weights)
            loss.backward()
            self.optimizer.step()

            pred_choice = seg_pred.cpu().data.max(1)[1].numpy()
            correct = np.sum(pred_choice == batch_label)
            total_correct += correct
            total_seen += (bs * points.shape[-1])
            loss_sum += loss

        return loss_sum / num_batches, total_correct / float(total_seen)
