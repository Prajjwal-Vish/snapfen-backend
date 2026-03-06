♟️ SnapFen - Instant Chess Analysis

SnapFen is a modern, full-stack web application that bridges the gap between physical boards (or uncopyable videos/streams) and digital analysis. It uses Computer Vision and a fine-tuned Convolutional Neural Network (CNN) to instantly convert screenshots of chessboards into standard FEN (Forsyth-Edwards Notation) strings.

✨ Features

🧠 AI-Powered Detection: Automatically detects chessboards from raw screenshots using OpenCV algorithms (Contours, Morphological Grids, Hough Lines).

🎯 Highly Accurate Recognition: Uses a custom-trained TensorFlow Lite CNN model with voting logic to classify pieces even in varying colors and styles.

⚡ Smart Paste (Ctrl+V): Skip the file explorer. Just copy an image to your clipboard and paste it directly onto the site for instant processing.

✂️ Manual Cropping: Built-in Cropper.js integration for tricky mobile screenshots or heavily obstructed boards.

🔄 Perspective & Turn Control: Easily toggle between White/Black POV and set the side to move to generate the perfect FEN.

🔗 1-Click Analysis: Instantly open your generated position in Lichess or Chess.com analysis boards.

🔐 User Accounts & History: Sign up to keep a personalized history of your recent scans, complete with visual thumbnails.

🚀 Modern UI: A sleek, responsive, glassmorphic interface built with Tailwind CSS.
