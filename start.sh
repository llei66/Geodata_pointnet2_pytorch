data=${1:-../data/train_test_whole_class_1km}
python  train.py  --model pointnet  --log-dir pointnet2_sem_seg_testll --batch-size 16  --data-path $data --blocks-per-epoch 2048
