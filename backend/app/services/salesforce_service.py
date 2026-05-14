import os
import logging
from app.services.graph_service import GraphService, GraphServiceError

logger = logging.getLogger(__name__)

# HighWire Salesforce Email-to-Case address
TICKET_EMAIL = os.getenv("TICKET_EMAIL", "helpdesk@highwirepress.com")
CC_EMAILS = os.getenv("TICKET_CC_EMAILS", "").split(",") if os.getenv("TICKET_CC_EMAILS") else []


def create_salesforce_case(subject: str, description: str, email: str, chat_history: str = ""):
    """
    Creates a Salesforce Case using HighWire's Email-to-Case system.
    Sends email to helpdesk@highwirepress.com which automatically creates a Salesforce ticket.
    """
    
    try:
        graph_service = GraphService()
        
        # Format email body for Salesforce Email-to-Case
        email_body = f"""
        <html>
        <body>
            <p><strong>HighWire Support Request from Chatbot</strong></p>
            
            <p><strong>Contact Email:</strong> {email}</p>
            <p><strong>Origin:</strong> Chatbot</p>
            
            <hr>
            
            <h3>Issue Description</h3>
            <p>{description}</p>
            
            <hr>
            
            <h3>Chat Conversation History</h3>
            <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; font-family: monospace; white-space: pre-wrap;">
{chat_history if chat_history else 'No chat history available.'}
            </div>
            
            <hr>
            <p style="color: #666; font-size: 12px;">
                <em>This ticket was automatically created by the HighWirePress Support Chatbot.</em>
            </p>
        </body>
        </html>
        """
        
        # Send email to helpdesk
        ticket_subject = f"[Chatbot Support] {subject}"
        
        graph_service.send_email(
            to_email=TICKET_EMAIL,
            subject=ticket_subject,
            body_html=email_body,
            cc_emails=CC_EMAILS
        )
        
        logger.info(f"Salesforce ticket email sent to {TICKET_EMAIL} for user {email}")
        
        return {
            "id": "SALESFORCE_EMAIL_SENT",
            "status": "Ticket created",
            "message": "Your support ticket has been created. You will receive a confirmation email shortly."
        }
        
    except GraphServiceError as e:
        logger.error(f"Failed to send Salesforce Email-to-Case: {e}")
        return {
            "id": "ERROR",
            "error": str(e),
            "message": "Failed to create support ticket. Please contact support directly at helpdesk@highwirepress.com"
        }
    except Exception as e:
        logger.error(f"Unexpected error creating Salesforce case: {e}")
        return {
            "id": "ERROR",
            "error": str(e),
            "message": "An unexpected error occurred. Please contact support directly at helpdesk@highwirepress.com"
        }
