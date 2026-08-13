import kagglehub
import os
import shutil

path = kagglehub.dataset_download(
    "suhanigupta04/student-placement-prediction-dataset"
)

print("Downloaded to:", path)
print("Files:")

for root, dirs, files in os.walk(path):
    for file in files:
        print(os.path.join(root, file))