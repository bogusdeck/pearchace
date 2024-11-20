# email.py
import logging
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from django.conf import settings

logger = logging.getLogger(__name__)

admin = "tanish.vashisth@xtagelabs.com"

def send_welcome_email(to_email, user_name):
    logger.info(f"Preparing to send welcome email to {to_email} for user {user_name}")
    message = Mail(
        from_email=settings.DEFAULT_FROM_EMAIL,
        to_emails=to_email,
        subject="Welcome to Our Shopify App!",
        html_content=f"""
            <h1>Welcome, {user_name}!</h1>
            <p>Thank you for installing our app. We're excited to have you on board!</p>
            <p>If you have any questions, feel free to reach out.</p>
        """
    )
    try:
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        logger.debug("Sending email through SendGrid API.")
        response = sg.send(message)
        logger.info(f"Welcome email sent successfully to {to_email}. Status code: {response.status_code}")
        return response.status_code, response.body, response.headers
    except Exception as e:
        logger.error(f"Error sending welcome email to {to_email}: {e}")
        return 500, None, None  

def order_not_found(errorr,user_name):
    logger.info(f"Preparing to send warning mail to admin ")
    message = Mail(
        from_mail = settings.DEFAULT_FROM_EMAIL,
        to_email = admin,
        subject = "We are not able to get the orders from the shopify",
        html_content=f"""
        <h1> Our app PEARCH is not able to fetch orders from shopify {user_name}<h1>
        <p> having this error <p>
        <p> {errorr} <p>
        """
    )
    try:
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        logger.debug("sending error logs to the admin")
        response = sg.send(message)
        logger.info(f"email sent successful to admin. Status code: {response.status_code}")
        return response.status_code, response.body, response.headers
    except Exception as e:
        logger.error(f"Error sending order not found email to admin : {e}")
        return 500, None, None
    
def products_not_found(errorr,user_name):
    logger.info(f"Preparing to send warning mail to admin")
    message = Mail(
        from_mail = settings.DEFAULT_FROM_EMAIL,
        to_email = admin,
        subject = "We are not able to get the products from the shopify",
        html_content=f"""
        <h1> Our app PEARCH is not able to fetch products from shopify {user_name}<h1>
        <p> having this error <p>
        <p> {errorr} <p>
        """
    )
    try:
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        logger.debug("sending error logs to the admin")
        response = sg.send(message)
        logger.info(f"email sent successful to admin. Status code: {response.status_code}")
        return response.status_code, response.body, response.headers
    except Exception as e:
        logger.error(f"Error sending products not found email to admin : {e}")
        return 500, None, None
    
