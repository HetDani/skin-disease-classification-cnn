from flask import *  
from PIL import Image
import io
import jsonpickle
import base64
import os

from tensorflow.keras.models import load_model
from PIL import Image, ImageOps #Install pillow instead of PIL
import numpy as np

app = Flask(__name__)  

np.set_printoptions(suppress=True)
model = load_model(os.path.join('sdp', 'gnew_model.h5'), compile=False)
class_names = open(os.path.join('sdp', 'gnew_labels.txt'), 'r').readlines()
data = np.ndarray(shape=(1, 224, 224, 3), dtype=np.float32)

size = (224, 224)

@app.route('/classify', methods=['GET','POST'])  
def init(): 
    if request.method == 'POST':
        location = request.args.get("location")

        imgpath = 'sdp/static/disease_photos/'+location
        print(imgpath)
        image = Image.open(imgpath).convert('RGB')

        image = ImageOps.fit(image, size, Image.LANCZOS)
        #image = ImageOps.fit(image, size, Image.ANTIALIAS)
        image_array = np.asarray(image)

        normalized_image_array = (image_array.astype(np.float32) / 127.0) - 1

        data[0] = normalized_image_array

        prediction = model.predict(data)
        index = np.argmax(prediction)
        class_name = class_names[index]
        confidence_score = prediction[0][index]

        #return class_name 
        return jsonify({"class_name":class_name})

if __name__ == '__main__':  
    app.run(debug=False,port=5052)
