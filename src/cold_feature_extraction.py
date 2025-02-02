# -*- coding: utf-8 -*-
"""
Created on Fri Dec 11 16:26:30 2020

@author: swati
"""
import imutils
from PIL import Image, ImageEnhance
import cv2
import matplotlib.pyplot as plt
import numpy as np

N_RHO_BINS = 7
N_ANGLE_BINS = 12
N_BINS = N_RHO_BINS * N_ANGLE_BINS
BIN_SIZE = 360 // N_ANGLE_BINS
R_INNER = 5.0
R_OUTER = 35.0
K_S = np.arange(3, 8)

class Cold():
    def __init__(self, params):
        self.sharpness_factor = params[0]
        self.bordersize = params[1]
        self.show_images = params[2]
        self.is_binary = params[3]
        
    def preprocess_binary_image(self, im, sharpness_factor = 10, bordersize = 3):
        
        kernel = np.ones((3, 3))
        img = cv2.morphologyEx(im, cv2.MORPH_CLOSE, kernel)
        img = cv2.medianBlur(img, 3)
        (thresh, img) = cv2.threshold(img, 128, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        im = Image.fromarray(img)
        enhancer = ImageEnhance.Sharpness(im)
        im_s_1 = enhancer.enhance(sharpness_factor)
        # plt.imshow(im_s_1, cmap='gray')
        image = 255 - np.array(im_s_1)
        bw_image = cv2.copyMakeBorder(
            image,
            top=bordersize,
            bottom=bordersize,
            left=bordersize,
            right=bordersize,
            borderType=cv2.BORDER_CONSTANT,
            value=[255]
        )
        # plt.imshow(bw_image, cmap='gray')
        return bw_image, image
    
    
    def preprocess_image(self, img_file, sharpness_factor = 10, bordersize = 3):
        im = Image.open(img_file)
        
        enhancer = ImageEnhance.Sharpness(im)
        im_s_1 = enhancer.enhance(sharpness_factor)
        # plt.imshow(im_s_1, cmap='gray')
        
        (width, height) = (im.width * 2, im.height * 2)
        im_s_1 = im_s_1.resize((width, height))
        if self.show_images: plt.imshow(im_s_1, cmap='gray')
        image = np.array(im_s_1)
        image = cv2.copyMakeBorder(
            image,
            top=bordersize,
            bottom=bordersize,
            left=bordersize,
            right=bordersize,
            borderType=cv2.BORDER_CONSTANT,
            value=[255, 255, 255]
        )
        orig_image = image.copy()
        
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        image = cv2.GaussianBlur(image,(3,3),0)
        if self.show_images: plt.imshow(image, cmap='gray')
        (thresh, bw_image) = cv2.threshold(image, 128, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        if self.show_images: plt.imshow(bw_image, cmap='gray')
        return bw_image, orig_image

    def get_contour_pixels(self, bw_image):
        contours, _= cv2.findContours(
            bw_image, cv2.RETR_TREE, 
            cv2.CHAIN_APPROX_NONE
            ) 
        # contours = imutils.grab_contours(contours)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[1:]
        
        img2 = bw_image.copy()[:,:,np.newaxis]
        img2 = np.concatenate([img2, img2, img2], axis = 2)
        if self.show_images:
            for cnt in contours : 
                cv2.drawContours(img2, [cnt], 0, (255, 0, 0), 1)  
                
            plt.imshow(img2, cmap='gray')
        return contours
    
    def get_cold_features(self, img_file, approx_poly_factor = 0.01):
        if self.is_binary:
            bw_image, _ = self.preprocess_binary_image(img_file, self.sharpness_factor, self.bordersize)
        else:
            bw_image, _ = self.preprocess_image(img_file, self.sharpness_factor, self.bordersize)
        contours = self.get_contour_pixels(bw_image)
        
        rho_bins_edges = np.log10(np.linspace(R_INNER, R_OUTER, N_RHO_BINS))
        feature_vectors = np.zeros((len(K_S), N_BINS))
        
        # print([len(cnt) for cnt in contours])
        for j, k in enumerate(K_S):
            hist = np.zeros((N_RHO_BINS, N_ANGLE_BINS))
            for cnt in contours:
                epsilon = approx_poly_factor * cv2.arcLength(cnt,True)
                cnt = cv2.approxPolyDP(cnt,epsilon,True)
                n_pixels = len(cnt)
                
                point_1s = np.array([point[0] for point in cnt])
                x1s, y1s = point_1s[:, 0], point_1s[:, 1]
                point_2s = np.array([cnt[(i + k) % n_pixels][0] for i in range(n_pixels)])
                x2s, y2s = point_2s[:, 0], point_2s[:, 1]
                
                thetas = np.degrees(np.arctan2(y2s - y1s, x2s - x1s) + np.pi)
                rhos = np.sqrt((y2s - y1s) ** 2 + (x2s - x1s) ** 2)
                rhos_log_space = np.log10(rhos)
                
                quantized_rhos = np.zeros(rhos.shape, dtype=int)
                for i in range(N_RHO_BINS):
                    quantized_rhos += (rhos_log_space < rho_bins_edges[i])
                    
                for i, r_bin in enumerate(quantized_rhos):
                    theta_bin = int(thetas[i] // BIN_SIZE) % N_ANGLE_BINS
                    hist[r_bin - 1, theta_bin] += 1
                
            normalised_hist = hist / hist.sum()
            feature_vectors[j] = normalised_hist.flatten()
            
        return feature_vectors.flatten()


if __name__ == '__name__':
    import argparse
    parser = argparse.ArgumentParser(description="")
    parser.add_argument("--img_file", type=str, default=r"IMAGE FILE LOCATION")
    parser.add_argument("--sharpness_factor", type=int, default=10)
    parser.add_argument("--bordersize", type=int, default=3)
    parser.add_argument("--show_images", type=bool, default=False)
    parser.add_argument("--is_binary", type=bool, default=False)
    opt = parser.parse_args()
    
    cold = Cold(opt)
    feature_vectors = cold.get_cold_features(opt.img_file)
    
    print ("shape of feature vector: {}".format(feature_vectors.shape))


