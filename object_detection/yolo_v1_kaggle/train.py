import sys

sys.path.append('../input')
print(sys.path)

from torchvision import models
from torch.utils.data import DataLoader
from yolov1.yolo_v1_kaggle.yolo_loss import yoloLoss
from yolov1.yolo_v1_kaggle.yolo_dataset import yolo_Dataset
from yolov1.yolo_v1_kaggle.models.resnet import resnet50
import torch
import os
import numpy as np


def main(best_model=False):
    data_root = '/kaggle/input/pascal-voc-2012/VOC2012'
    learning_rate = 0.001
    num_epochs = 50
    best_val_loss = np.inf
    if device == 'cpu':
        batch_size = 4
    elif best_model:
        batch_size = 8
    else:
        batch_size = 64

    # ============================= create module =============================
    net = resnet50()
    # print(summary(net, (3, 224, 224), 8))

    if best_model:
        net.load_state_dict(torch.load('/kaggle/input/yolov1/yolo_v1_kaggle/best.pth'))
    else:
        # 获取取训练好模型
        resnet = models.resnet50(weights=models.ResNet50_Weights.DEFAULT)
        # 提取模型中的参数字典： {'参数名称':参数, ...}
        new_state_dict = resnet.state_dict()
        # 提取自己搭建的模型的参数字典： {'参数名称':参数, ...}
        dd = net.state_dict()
        pretrained_layer_name = []
        for k in new_state_dict.keys():
            if k in dd.keys() and not k.startswith('fc'):
                pretrained_layer_name.append(k)
                dd[k] = new_state_dict[k]
        net.load_state_dict(dd)

    net.to(device)

    # ============================= dataset & dataloader =============================
    image_path = os.path.join(data_root, "JPEGImages")
    train_txt = '/kaggle/input/yolov1/yolo_v1_kaggle/my_yolo_dataset/train_label_bbox.txt'
    val_txt = '/kaggle/input/yolov1/yolo_v1_kaggle/my_yolo_dataset/val_label_bbox.txt'
    train_dataset = yolo_Dataset(image_path, train_txt, train=True)
    val_dataset = yolo_Dataset(image_path, val_txt, train=False)

    nw = min([os.cpu_count(), batch_size if batch_size > 1 else 0, 8])
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=nw)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, num_workers=nw)

    print('the dataset has %d images' % (len(train_dataset)))
    print('the batch_size is %d' % (batch_size))

    # ============================= optimizer & loss function =============================
    params = []

    if not best_model:
        for i, (name, param) in enumerate(net.named_parameters()):
            if name in pretrained_layer_name:
                param.requires_grad = False
        params = [p for p in net.parameters() if p.requires_grad]
    optimizer = torch.optim.SGD(params, lr=learning_rate, momentum=0.9, weight_decay=5e-4)

    criterion = yoloLoss(14, 2, 5, 0.5)

    # ============================= train & validation =============================

    for epoch in range(num_epochs):

        net.train()
        if epoch == 1:
            learning_rate = 0.0005
        if epoch == 2:
            learning_rate = 0.00075
        if epoch == 3:
            learning_rate = 0.001
        if epoch == 30:
            learning_rate = 0.0001
        if epoch == 40:
            learning_rate = 0.00001

        for param_group in optimizer.param_groups:
            param_group['lr'] = learning_rate

        # === train ===
        net.train()
        total_loss = 0.
        for i, (image, target) in enumerate(train_loader):
            image, target = image.to(device), target.to(device)
            pred = net(image)
            loss = criterion(pred, target)
            # total_loss += loss.item()

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            if i % 5 == 0:
                print("epoch : {}, step : {}, loss : {}".format(epoch, i, loss))

        # === valid ===
        validation_loss = 0.0
        net.eval()
        for i, (image, target) in enumerate(val_loader):
            image, target = image.to(device), target.to(device)
            pred = net(image)
            loss = criterion(pred, target)
            validation_loss += loss.item()
            if i % 5 == 0:
                print("epoch : {}, step : {}, loss : {}".format(epoch, i, loss))
        validation_loss /= len(val_loader)

        if best_val_loss > validation_loss:
            best_val_loss = validation_loss
            print('get best test loss %.5f' % best_val_loss)
            torch.save(net.state_dict(), 'best.pth')

        torch.save(net.state_dict(), 'yolo.pth')


if __name__ == '__main__':
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print('using device : ', device)

    main()