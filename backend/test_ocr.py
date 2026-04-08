from PIL import Image
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Users\Venkata.Jakkinapalli\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
img = Image.open(r"C:\Users\Venkata.Jakkinapalli\chatbot2\backend\uploads\1\test.png")
print(pytesseract.image_to_string(img))