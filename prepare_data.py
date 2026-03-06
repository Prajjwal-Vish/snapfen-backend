import tensorflow as tf
from tensorflow.keras.preprocessing.image import ImageDataGenerator
import numpy as np
import os
import matplotlib.pyplot as plt

# --- Configuration ---
DATA_DIR = r'C:\Users\GFG19761\Desktop\img_to_fen\raw_data' # Replace with the actual path to your 'chess_folders' directory
IMAGE_SIZE = (64, 64)      # Resize all images to this resolution (e.g., 64x64 pixels)
BATCH_SIZE = 32            # How many images to process at once
VAL_SPLIT = 0.2            # 20% of your data will be used for validation

# --- 1. Load Data with ImageDataGenerator ---
# This is a very convenient way to load images from directories
# and automatically label them based on folder names.

print(f"Loading images from: {DATA_DIR}")

# Create an ImageDataGenerator for training data
# We'll apply some basic augmentations to make the model more robust
train_datagen = ImageDataGenerator(
    rescale=1./255,          # Normalize pixel values to 0-1
    rotation_range=10,       # Randomly rotate images by up to 10 degrees
    width_shift_range=0.1,   # Randomly shift images horizontally
    height_shift_range=0.1,  # Randomly shift images vertically
    zoom_range=0.1,          # Randomly zoom into images
    horizontal_flip=True,    # Randomly flip images horizontally (good for pieces like rooks, bishops)
    fill_mode='nearest',     # How to fill new pixels created by transformations
    validation_split=VAL_SPLIT # Split data for validation
)

# Create an ImageDataGenerator for validation data (only rescale)
val_datagen = ImageDataGenerator(
    rescale=1./255,          # Normalize pixel values
    validation_split=VAL_SPLIT
)

# Flow images from directories
train_generator = train_datagen.flow_from_directory(
    DATA_DIR,
    target_size=IMAGE_SIZE,
    batch_size=BATCH_SIZE,
    class_mode='categorical', # Important: for multiple classes, output one-hot encoded labels
    subset='training',        # Use the training split
    color_mode='rgb'          # Ensure images are loaded in RGB (3 channels)
)

validation_generator = val_datagen.flow_from_directory(
    DATA_DIR,
    target_size=IMAGE_SIZE,
    batch_size=BATCH_SIZE,
    class_mode='categorical',
    subset='validation',      # Use the validation split
    color_mode='rgb'
)

# Get the class names (folder names) and their corresponding indices
class_names = list(train_generator.class_indices.keys())
num_classes = len(class_names)

print(f"\nFound {train_generator.samples} training images belonging to {num_classes} classes.")
print(f"Found {validation_generator.samples} validation images belonging to {num_classes} classes.")
print(f"Class names: {class_names}")

# --- 2. Optional: Visualize a batch of images and labels ---
def plot_images(generator):
    images, labels = next(generator) # Get a batch of images and labels
    plt.figure(figsize=(10, 10))
    for i in range(min(16, len(images))): # Plot up to 16 images
        ax = plt.subplot(4, 4, i + 1)
        plt.imshow(images[i])
        # Get the original class name from the one-hot encoded label
        label_index = np.argmax(labels[i])
        plt.title(class_names[label_index])
        plt.axis("off")
    plt.show()

# Uncomment the line below to visualize some training images
# plot_images(train_generator)

print("\nData loading and preprocessing complete. You can now use 'train_generator' and 'validation_generator' for model training.")
print("The 'class_names' list maps numerical labels back to their original names.")
print(f"Number of classes detected: {num_classes}")

# You would save these generators or pass them to your model training script
# For now, we'll stop here to process this step.
# The next step will be defining and training your model using these generators.