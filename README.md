# Fun Fana – Self-Service Keychain Ordering System

Customer-facing web app for your physical shop.  
Customers scan a QR code → place order on their phone → order is sent automatically to your email.

---

## Features

- Mobile-friendly ordering page
- Custom name keychain (50 EGP each)
- Quantity selection
- 16 colors
- Customer info: Name, Phone, Email
- Payment: Cash or Instapay (shows 01274444082)
- Optional payment screenshot upload
- Automatic order number
- Exact confirmation date & time
- Estimated ready time: 4–5 working days
- Order + screenshot automatically emailed to **fun.funa.eg@gmail.com**

---

## Quick Start

### 1. Install dependencies

```bash
cd fun_fana_order_system
pip install -r requirements.txt
```

### 2. Configure email (required for automatic emails)

```bash
cp .env.example .env
```

Open the `.env` file and add your **Gmail App Password**:

```
SENDER_EMAIL=fun.funa.eg@gmail.com
SENDER_PASSWORD=xxxx xxxx xxxx xxxx
```

**How to get a Gmail App Password:**
1. Go to [https://myaccount.google.com/security](https://myaccount.google.com/security)
2. Make sure **2-Step Verification** is turned ON
3. Search for **App passwords**
4. Select app: **Mail** → Create
5. Copy the 16-character password and paste it in `.env`

### 3. Run the system

```bash
python main.py
```

Open in browser: **http://localhost:8000**

---

## For the Shop (QR Code)

1. Run the system on a computer that stays online in the shop (or host it online later).
2. Generate a QR code that points to the website address.
3. Print the QR code and put it in a visible place in the shop.

Customers scan → order → you receive the email instantly.

---

## Order Email

Every new order is sent to **fun.funa.eg@gmail.com** with:
- Order number
- Exact date & time
- Customer details
- Keychain name + color + quantity
- Total price
- Payment method
- Screenshot attachment (if customer uploaded one)

---

## Files

| File / Folder       | Purpose                          |
|---------------------|----------------------------------|
| `main.py`           | Backend + email logic            |
| `templates/index.html` | Customer ordering page         |
| `uploads/`          | Payment screenshots              |
| `orders.db`         | Local order history (created automatically) |
| `.env`              | Email password (do not share)    |

---

## Notes

- Price is fixed at **50 EGP** per keychain.
- Maximum quantity: 50.
- The system works fully offline except for sending the email.
