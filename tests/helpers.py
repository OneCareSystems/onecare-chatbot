from django.core.files.uploadedfile import SimpleUploadedFile

from knowledgebase import services

from .pdfs import english_pdf

TOKEN = "t" * 40


def auth(user="42"):
    headers = {"HTTP_AUTHORIZATION": f"Bearer {TOKEN}"}
    if user is not None:
        headers["HTTP_X_ONECARE_USER_ID"] = user
    return headers


def pdf_file(data=None, name="doc.pdf"):
    return SimpleUploadedFile(name, data or english_pdf("seed document"), "application/pdf")


def new_pdf_doc(actor="42"):
    return services.upload_pdf(uploaded_file=pdf_file(), title="Test doc", actor=actor)


LONG_EN = " ".join(f"paracetamol{i % 7} dosage fever adults{i % 5}" for i in range(300))