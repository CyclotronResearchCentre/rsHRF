from spm import *
import numpy as np
import os
from wgr_rshrf_estimation_canonhrf2dd_par2 import *
from wgr_get_parameters import *
import matplotlib.pyplot as plt
from scipy import stats, signal
import scipy.io as sio

"""
Mask File
"""
brainmask = 'mask_3mm_278ROIs.nii'

v = spm_vol(brainmask)
brain = spm_read_vols(v)
voxel_ind = np.where(brain==11)[0] # change as you like. brain>0 for all brain, or brain==ROIid
num_voxel = len(voxel_ind)

"""
PARAMETERS
"""
temporal_mask = []

TR = 2
para = {}

para['TR'] = TR

para['T'] = 3

para['T0'] = 3

if para['T'] == 1:
    para['T0'] = 1

para['dt'] = para['TR'] / para['T']

para['TD_DD'] = 2

para['AR_lag'] = 1

para['thr'] = 1

para['len'] = 24

para['lag'] = np.arange(np.fix(3/para['dt']),np.fix(9/para['dt'])+1,dtype='int')

"""
fMRI Data
"""
main = os.getcwd()

save_dir = os.path.join(main,'output_HRF_Deconv')

if not os.path.isdir(save_dir):
    os.mkdir(save_dir)

sub = [os.path.join(main,'input_BOLD_data\sub_001\processed_fmri_data_4D.nii')]

for isub in range(len(sub)):
    print('Reading data ...')
    sub_dir = os.path.dirname(sub[isub])
    name, ext = os.path.basename(sub[isub]).split('.')
    name = name.split('\\')[-1]

    sub_save_dir = sub_dir.replace(main,save_dir)

    v1 = spm_vol(sub[isub].replace('\\','/'))

    if(v1.header.get_data_shape()[:-1]!=v.header.get_data_shape()):
        print('The dimension of your mask is different than the one of your fMRI data!')
        continue
    else:
        data = v1.get_data()
        nobs = data.shape[3]
        data1 = np.reshape(data, (-1, nobs), order='F').T
        bold_sig = data1[:, voxel_ind]
        data_deconv = np.zeros(bold_sig.shape)

        print('Retrieving HRF ...')
        beta_hrf, bf, event_bold = wgr_rshrf_estimation_canonhrf2dd_par2(bold_sig,para,temporal_mask)

        hrfa = np.dot(bf,beta_hrf[np.arange(0,bf.shape[1]),:])
        hrf1 = hrfa[:,0]

        nvar = hrfa.shape[1]
        PARA = np.zeros((3,nvar))

        for voxel_id in range(nvar):
            hrf1 = hrfa[:, voxel_id]
            PARA[:, voxel_id] = wgr_get_parameters(hrf1, para['TR'] / para['T'])

        print('Done')

        print('Deconvolving HRF ...')

        T = np.around(para['len']/TR)

        if para['T'] > 1:
            hrfa_TR = signal.resample_poly(hrfa, 1, para['T'])
        else:
            hrfa_TR = hrfa

        for voxel_id in range(nvar):
            hrf = hrfa_TR[:,voxel_id]
            H = np.fft.fft(np.append(hrf,np.zeros((nobs-max(hrf.shape),1))),axis=0)
            M = np.fft.fft(bold_sig[:,voxel_id])
            data_deconv[:,voxel_id] = np.fft.ifft(H.conj()*M/(H*H.conj()+2))

        sio.savemat(os.path.join(sub_save_dir,name+'_hrf.mat'),{'para':para,'hrfa':hrfa,'event_bold':event_bold,'PARA':PARA})
        HRF_para_str = ['Height.nii','Time2peak.nii','FWHM.nii']
        data = np.zeros(v.get_data().shape).flatten(order='F')

        for i in range(3):
            fname = os.path.join(sub_save_dir,name+'_'+HRF_para_str[i])
            data[voxel_ind] = PARA[i,:]
            data = data.reshape(v.get_data().shape,order='F')
            spm_write_vol(v,data,fname)
            data = data.flatten(order='F')

        data = np.zeros(v1.get_data().shape)
        dat3 = np.zeros(v1.header.get_data_shape()[:-1]).flatten(order='F')
        for i in range(nobs):
            fname = os.path.join(sub_save_dir,name+'_deconv')
            dat3[voxel_ind] = data_deconv[i,:]
            dat3 = dat3.reshape(v1.header.get_data_shape()[:-1],order='F')
            data[:,:,:,i] = dat3
            dat3 = dat3.flatten(order='F')
        spm_write_vol(v1, data, fname)

        plt.plot(hrfa[:,0],linewidth=1)
        plt.show()

        plt.plot(stats.zscore(bold_sig[:,0],ddof=1),linewidth=1)
        plt.plot(stats.zscore(data_deconv[:,0],ddof=1),color='r',linewidth=1)
        markerline, stemlines, baseline = plt.stem(event_bold[0].toarray()[0])
        plt.setp(baseline,'color','k','markersize',1)
        plt.setp(stemlines,'color','k','markersize',1)
        plt.setp(markerline,'color','k','markersize',3,'marker','d')
        plt.legend(['BOLD','deconvolved','events'])
        plt.show()
