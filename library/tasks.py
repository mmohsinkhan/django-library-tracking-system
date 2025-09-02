from collections import defaultdict
from celery import shared_task
from .models import Loan
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from .models import Loan

@shared_task
def send_loan_notification(loan_id):
    try:
        loan = Loan.objects.get(id=loan_id)
        member_email = loan.member.user.email
        book_title = loan.book.title
        send_mail(
            subject='Book Loaned Successfully',
            message=f'Hello {loan.member.user.username},\n\nYou have successfully loaned "{book_title}".\nPlease return it by the due date.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[member_email],
            fail_silently=False,
        )
    except Loan.DoesNotExist:
        pass


@shared_task
def check_overdue_loans():
    loan_records = Loan.objects.all().filter(is_returned=False, due_date__lt=timezone.now().date()).select_related(
        'book', 'member', 'member__user'
    )
    overdue_loans = defaultdict(list) # User emails to books map
    for loan in loan_records:
        email = loan.member.user.email
        book = loan.book.title
        overdue_loans[email].append(book)
    # Send emails
    for email, books in overdue_loans.items():
        books_str = ', '.join(books)
        send_mail(
            subject='Overdue Loans',
            message=f'Hello {email},\n\nYour submission is due for the following books.\n{books_str}',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
