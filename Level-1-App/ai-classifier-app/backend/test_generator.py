# test_generator.py — Generate Random Test Files for Classification
# =================================================================
# Creates realistic customer feedback files in various formats
# (TXT, PDF, DOCX) across all 4 categories as in-memory bytes.
# Returns a list of (filename, category, bytes) tuples for ZIP packaging.

import random
from datetime import datetime, timezone
from io import BytesIO

import fitz  # PyMuPDF
from docx import Document
from file_organizer import VALID_CATEGORIES

# ---------------------
# Sample feedback texts per category
# ---------------------

COMPLAINT_TEXTS = [
    "My order has not arrived for 3 weeks and customer service is completely unhelpful.",
    "The product broke after just 2 days of use. Terrible quality, I want a full refund.",
    "Your app keeps crashing every 5 minutes. This is the worst experience I've ever had.",
    "I was charged twice for the same order and nobody is responding to my emails.",
    "The delivery driver left my package in the rain and everything inside was damaged.",
    "I've been on hold for over an hour trying to reach your support team. Unacceptable!",
    "The item I received looks nothing like the photos on your website. Total false advertising.",
    "Your website logged me out and I lost my entire shopping cart. Fix your broken system!",
    "The warranty claim was rejected for no valid reason. This is very frustrating.",
    "I ordered a blue shirt but received a red one. This is the third time you sent wrong items.",
    "Your service has gone downhill dramatically. I used to love this company but not anymore.",
    "The food delivery arrived 2 hours late and the food was completely cold and soggy.",
]

SUGGESTION_TEXTS = [
    "It would be great if you added a dark mode option to your mobile app.",
    "Please consider adding a live chat feature to your website for faster support.",
    "You should offer a loyalty rewards program for frequent customers.",
    "Adding a wishlist feature would make the shopping experience much better.",
    "It would be helpful to have order tracking with real-time GPS updates.",
    "Please add multi-language support, especially Turkish and German.",
    "A subscription-based model with monthly deliveries would be awesome.",
    "You should integrate Apple Pay and Google Pay for faster checkout.",
    "Adding a product comparison tool would help customers make better decisions.",
    "It would be nice to have email notifications when items go on sale.",
    "Please consider adding a student discount program for university students.",
    "A mobile widget showing order status on the home screen would be very useful.",
]

QUESTION_TEXTS = [
    "How do I change my billing date? I could not find it in the settings section.",
    "What is your return policy for items purchased during the holiday sale?",
    "Can I use multiple discount codes on a single order? The FAQ doesn't mention this.",
    "Where can I find the tracking number for my recent order?",
    "Is it possible to change my shipping address after placing an order?",
    "Do you ship internationally? I need to send a gift to Germany.",
    "What payment methods do you accept? I only have a prepaid Visa card.",
    "How long does the refund process usually take after returning an item?",
    "Can I schedule a specific delivery time for my next order?",
    "What is the maximum file size for uploading documents to your portal?",
    "How do I link my old account with my new email address?",
    "Are there any upcoming promotions or Black Friday deals I should know about?",
]

PRAISE_TEXTS = [
    "Your customer support team is absolutely fantastic! Best service I've ever received.",
    "I love the new app update! The interface is so much cleaner and faster now.",
    "Amazing product quality! I've been using it for 6 months and it still works perfectly.",
    "The delivery was incredibly fast — ordered yesterday and it arrived this morning!",
    "Your team went above and beyond to help me with my issue. Thank you so much!",
    "Best online shopping experience ever. The website is intuitive and easy to use.",
    "The packaging was beautiful and eco-friendly. Love the attention to detail!",
    "Sarah from your support team deserves a raise. She was incredibly helpful and patient.",
    "I recommended your service to all my friends. Keep up the great work!",
    "The new feature you released last week is exactly what I needed. Perfect timing!",
    "Your product exceeded my expectations in every way. Worth every penny!",
    "Five stars! The checkout process is seamless and the product arrived in perfect condition.",
]

CATEGORY_TEXTS = {
    "Complaint": COMPLAINT_TEXTS,
    "Suggestion": SUGGESTION_TEXTS,
    "Question": QUESTION_TEXTS,
    "Praise": PRAISE_TEXTS,
}


def _generate_txt(text: str) -> bytes:
    """Generate a plain text file."""
    return text.encode("utf-8")


def _generate_docx(text: str) -> bytes:
    """Generate a DOCX file with the given text."""
    doc = Document()
    doc.add_paragraph(text)
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _generate_pdf(text: str) -> bytes:
    """Generate a minimal PDF file with the given text."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=11)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def generate_test_files(count: int = 40) -> list[tuple[str, str, bytes]]:
    """
    Generate random test files across all categories and formats.

    Returns a list of (filename, category, content_bytes) tuples.
    Nothing is written to disk — caller decides what to do with them.
    """
    categories = list(VALID_CATEGORIES)
    formats = ["txt", "txt", "txt", "pdf", "pdf", "docx", "docx"]
    generated: list[tuple[str, str, bytes]] = []
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    # Distribute evenly across categories
    per_category = count // len(categories)
    remainder = count % len(categories)

    file_index = 0
    for cat in categories:
        cat_count = per_category + (1 if remainder > 0 else 0)
        remainder = max(0, remainder - 1)

        texts = CATEGORY_TEXTS[cat]

        for _ in range(cat_count):
            file_index += 1
            text = random.choice(texts)
            fmt = random.choice(formats)

            # Generate filename
            words = text.split()[:4]
            slug = "_".join(w.lower().strip(".,!?") for w in words)
            filename = f"test_{file_index:02d}_{slug}_{timestamp}.{fmt}"

            # Generate file content
            if fmt == "pdf":
                content = _generate_pdf(text)
            elif fmt == "docx":
                content = _generate_docx(text)
            else:
                content = _generate_txt(text)

            generated.append((filename, cat, content))

    return generated
