# Pytorch Implementation of PointNet and PointNet++ with Geodata


##Installation
- Clone this repo:
```buildoutcfg
git clone git@github.com:llei66/Geodata_pointnet2_pytorch.git
cd Geodata_pointnet2_pytorch
```
#### Environments:
```
Ubuntu 16.04 
Python 3.6.7 
Pytorch >= 11.5.1+cu92
```

#### Change to test_ll branch 
> This branch is easier to read, speed up and optimize the entire process.
```buildoutcfg
git checkout -b test_ll origin/test_ll
```
#### Choice
1. If you want to process the original .laz data, please step by step
2. If you want to train directly with samples, go [Semantic Segmentation](#jump)
3. If you use Colab, go Google drver and [GeoData_training](https://colab.research.google.com/drive/1cpAzWEQn3T408g6yM97IEwiQx8mLQoP8?authuser=1#scrollTo=ruN3V-x_r-SV)



## Predata with Geodata
### Introduction of Geodata
> [Datainfo](https://download.kortforsyningen.dk/content/dhmpunktsky)

### Download LAStools and comppile
```buildoutcfg
wget http://lastools.github.io/download/LAStools.zip
unzip LAStools.zip
```

### Download .laz data from ERDA samples or official website
- [ERDA samples](https://erda.dk/wsgi-bin/fileman.py?path=DeepCrop/)
  > ./DeepCrop/Datasets/GeoData/train_test_whole_class_1km/
### Use LAStools to convert .txt data
```buildoutcfg
sh LAStools/bin/las2txt.sh ${.laz} ${.txt}
```
### clear and crop Geodata

#### clear data with 1km *1km
```buildoutcfg
cd data_utils/pre_utils_data
python clear_geodata_1.py
```
## Use DublinCity datasets

### Introduction of DublinCityData

> [DataInfo](https://v-sense.scss.tcd.ie/dublincity/)

```
Download data from Erda
>  ./DeepCrop/Datasets/DublinCityData/TrainTestData/
```
## <a name='jump'> Semantic Segmentation </a>

### Dowdload train and test sample from Erda
```
wget https://sid.erda.dk/share_redirect/dJxtJ4Kysc
unzip train_test_whole_class_200m.zip -d ./data/
```
### Run

#### run with 250m * 250m subares of Geodata
```
sh train_geodata_crop_1.sh
```

#### run with the whole areas
```buildoutcfg
sh train_geodata_1.sh
```
#### run with DublinCityData
```buildoutcfg
sh train_dublin_1.sh
```
### Test and Visulize
```buildoutcfg
python test_vis_Geodata_crop_1.py
```

## Reference By
[halimacc/pointnet3](https://github.com/halimacc/pointnet3)<br>
[fxia22/pointnet.pytorch](https://github.com/fxia22/pointnet.pytorch)<br>
[charlesq34/PointNet](https://github.com/charlesq34/pointnet) <br>
[charlesq34/PointNet++](https://github.com/charlesq34/pointnet2) <br>
[yanx27/Pointnet_Pointnet2_pytorch](https://github.com/yanx27/Pointnet_Pointnet2_pytorch)



## based 
./scripts_config/README.md.config
