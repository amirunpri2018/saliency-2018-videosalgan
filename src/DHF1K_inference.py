import cv2
import os
import datetime
import numpy as np
from modules.clstm import ConvLSTMCell
import pickle
import torch
from torchvision import transforms, utils
import torch.backends.cudnn as cudnn
from torch import nn
from torch.utils import data
from torch.autograd import Variable
from data_loader import DHF1K_frames

dtype = torch.FloatTensor
if torch.cuda.is_available():
    dtype = torch.cuda.FloatTensor

clip_length = 10 #with 10 clips the loss seems to reach zero very fast
number_of_videos = 700 # DHF1K offers 700 labeled videos, the other 300 are held back by the authors
#pretrained_model = './SalConvLSTM.pt'
pretrained_model = './Ablated_Model_No_LSTM.pt'



#dst = "/imatge/lpanagiotis/work/DHF1K/clstm_predictions"
dst = "/imatge/lpanagiotis/work/DHF1K/abl_predictions"
# Parameters
params = {'batch_size': 1, # number of videos / batch, I need to implement padding if I want to do more than 1, but with DataParallel it's quite messy
          'num_workers': 4,
          'pin_memory': True}

def main():

    # =================================================
    # ================ Data Loading ===================

    #Expect Error if either validation size or train size is 1
    dataset = DHF1K_frames(
        number_of_videos = number_of_videos,
        clip_length = clip_length,
        split = None,
        transforms = transforms.Compose([
            transforms.ToTensor()
            ])
        )
         #add a parameter node = training or validation
    print("Size of test set is {}".format(len(dataset)))

    #print(len(dataset[0]))
    #print(len(dataset[1]))

    loader = data.DataLoader(dataset, **params)

    # =================================================
    # ================= Load Model ====================

    # Using same kernel size as they do in the DHF1K paper
    # Amaia uses default hidden size 128
    # input size is 1 since we have grayscale images
    model = ConvLSTMCell(use_gpu=True, input_size=1, hidden_size=128, kernel_size=3)

    temp = torch.load(pretrained_model)['state_dict']
    # Because of dataparallel there is contradiction in the name of the keys so we need to remove part of the string in the keys:.
    from collections import OrderedDict
    checkpoint = OrderedDict()
    for key in temp.keys():
        new_key = key.replace("module.","")
        checkpoint[new_key]=temp[key]

    model.load_state_dict(checkpoint, strict=True)
    print("Pre-trained model loaded succesfully")

    #model = nn.DataParallel(model).cuda()
    #cudnn.benchmark = True #https://discuss.pytorch.org/t/what-does-torch-backends-cudnn-benchmark-do/5936
    model = model.cuda()
    # ==================================================
    # ================== Inference =====================

    if not os.path.exists(dst):
        os.mkdir(dst)
    else:
        print("Be warned, you are about to write on an existing folder. If this is not intentional cancel now.")

    # switch to evaluate mode
    model.eval()

    for i, video in enumerate(loader):
        video_dst = os.path.join(dst, str(i+1))
        if not os.path.exists(video_dst):
            os.mkdir(video_dst)

        count = 0
        state = None # Initially no hidden state
        for j, (clip, gtruths) in enumerate(video):
            clip = Variable(clip.type(dtype).t(), requires_grad=False)
            gtruths = Variable(gtruths.type(dtype).t(), requires_grad=False)
            for idx in range(clip.size()[0]):
                #print(clip[idx].size()) #needs unsqueeze
                # Compute output
                (hidden, cell), saliency_map = model.forward(clip[idx], state)
                hidden = Variable(hidden.data)
                cell = Variable(cell.data)
                state = (hidden, cell)
                count+=1
                utils.save_image(saliency_map.data.cpu(), os.path.join(video_dst, "{}.png".format(str(count))))
                # j*clip_length+idx because we are iterating over batches of images and +1 because we don't want to start naming at 0
        print("Video {} done".format(i+1))

main()
