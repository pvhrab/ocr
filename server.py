import os, json, re, io, uuid, string, logging

from flask import Flask, request, redirect, url_for, send_from_directory
from werkzeug import secure_filename
from passporteye import read_mrz
from passporteye.mrz.text import MRZ
from passporteye.mrz.text import MRZOCRCleaner
from mimetypes import MimeTypes

from textwrap import wrap
from logging.handlers import RotatingFileHandler

from google.cloud import vision

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "./auth.json"

# Extensions Control
ALLOWED_EXTENSIONS = set(['pdf', 'png', 'jpg', 'jpeg', 'tiff', 'tif', 'jfif', 'PDF', 'JPEG', 'PNG', 'JPG', 'TIFF', 'TIF', 'JFIF'])
UPLOAD_FOLDER = 'uploads'

# Flask set limits
app = Flask(__name__)
app.config['TRAP_BAD_REQUEST_ERRORS'] = False
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Google Vision def
def detect_document(tempfile):
    """Detects document features in an image."""
    client = vision.ImageAnnotatorClient()

    with io.open(tempfile, 'rb') as image_file:
        content = image_file.read()
    
    # Security Check
    image = vision.types.Image(content=content)

    response = client.document_text_detection(image=image)
    document = response.full_text_annotation

    # Condition for retrive all blocks from Google OCR
    for page in document.pages:
        for block in page.blocks:
            block_words = []
            for paragraph in block.paragraphs:
                block_words.extend(paragraph.words)

            block_symbols = []
            for word in block_words:
                block_symbols.extend(word.symbols)

            block_text = ''
            for symbol in block_symbols:
                block_text = block_text + symbol.text

            m = block_text
            
            # MRZ data prepare for send to MRZ Class
            if m.find('P<') != -1 :
                if m[43] == '<' :
                    m = m[:44] + ' \n ' + m[44:]
                    # print(m)
                    mrz2 = MRZ.from_ocr(m)
                    return mrz2.to_dict() if mrz2 is not None else {'mrz_type': None, 'valid': False, 'valid_score': 0}
                else:
                    m = m[:43] + '< \n ' + m[43:]
                    mrz2 = MRZ.from_ocr(m)
                    return mrz2.to_dict() if mrz2 is not None else {'mrz_type': None, 'valid': False, 'valid_score': 0}

            elif m.find('I<', 0, 3) != -1 :
                m = m[:30] + ' \n ' + m[30:60] + ' \n ' + m[60:]
                # print(m)
                mrz2 = MRZ.from_ocr(m)
                return mrz2.to_dict() if mrz2 is not None else {'mrz_type': None, 'valid': False, 'valid_score': 0}

#            else:
#                return {'mrz_type': None, 'valid': False, 'valid_score': 0}

# Allowed extemsions control
def allowed_file(filename):
    return filename[-3:].lower() in ALLOWED_EXTENSIONS

# Web server GET/POST route /ocr
@app.route('/ocr', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        filei = request.files['file']
        if filei and allowed_file(filei.filename):
            # Mime Type Check
            mime = MimeTypes()
            mime_type, encoding = mime.guess_type(filei.filename)

            # Mime-Type condition
            if mime_type in ('image/png', 'image/tiff', 'image/jpeg', 'application/pdf'):

                print('**found file', filei.filename, mime_type)
                #filename = secure_filename(filei.filename)
                filename = str(uuid.uuid4())
                filei.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

                tempfile = './uploads/' + filename
                # Start OCR proccess with MRZ
                mrz1 = read_mrz(tempfile)

                # Python put data to dictionary
                d1 = mrz1.to_dict() if mrz1 is not None else {'mrz_type': None, 'valid': False, 'valid_score': 0}

                # Retrive valid_score
                valid_score = int(d1['valid_score'])

                # Check valid score condition
                if valid_score > 70:
                    os.remove(tempfile)
                    return json.dumps(d1, ensure_ascii=False)

                else:
                    d2 = detect_document(tempfile)
                    os.remove(tempfile)
                    return json.dumps(d2, ensure_ascii=False)


            else:
                return '{"status": "Error mime-type of uploaded file. File is not Image"}'

# For test GET type
    return '''
    <!doctype html>
    <title>Upload new File</title>
    <h1>Upload new File</h1>
    <form action="" method=post enctype=multipart/form-data>
      <p><input type=file name=file>
         <input type=submit value=Upload>
    </form>
    '''

# Web server handler starter
if __name__ == '__main__':
    # Logging
    handler = RotatingFileHandler('loggingweb.log', maxBytes=10000, backupCount=1)
    handler.setLevel(logging.INFO)
    app.logger.addHandler(handler)
    # Start web server with default host 127.0.0.1 and port 5000
    app.run(debug=False)
