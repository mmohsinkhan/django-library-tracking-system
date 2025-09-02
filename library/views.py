from datetime import timedelta
from django.db.models import Count, Q
from rest_framework import viewsets, generics, status
from rest_framework.response import Response
from .models import Author, Book, Member, Loan
from .serializers import AuthorSerializer, BookSerializer, MemberSerializer, LoanSerializer, ExtendDueDateSerializer
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from django.utils import timezone
from .tasks import send_loan_notification


class CustomPagination(PageNumberPagination):
    page_size_query_param = 'page_size'
    max_page_size = 1000


class AuthorViewSet(viewsets.ModelViewSet):
    queryset = Author.objects.all()
    serializer_class = AuthorSerializer

class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.all().select_related('author')
    serializer_class = BookSerializer
    pagination_class = CustomPagination

    @action(detail=True, methods=['post'])
    def loan(self, request, pk=None):
        book = self.get_object()
        if book.available_copies < 1:
            return Response({'error': 'No available copies.'}, status=status.HTTP_400_BAD_REQUEST)
        member_id = request.data.get('member_id')
        try:
            member = Member.objects.get(id=member_id)
        except Member.DoesNotExist:
            return Response({'error': 'Member does not exist.'}, status=status.HTTP_400_BAD_REQUEST)
        loan = Loan.objects.create(book=book, member=member)
        book.available_copies -= 1
        book.save()
        send_loan_notification.delay(loan.id)
        return Response({'status': 'Book loaned successfully.'}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def return_book(self, request, pk=None):
        book = self.get_object()
        member_id = request.data.get('member_id')
        try:
            loan = Loan.objects.get(book=book, member__id=member_id, is_returned=False)
        except Loan.DoesNotExist:
            return Response({'error': 'Active loan does not exist.'}, status=status.HTTP_400_BAD_REQUEST)
        loan.is_returned = True
        loan.return_date = timezone.now().date()
        loan.save()
        book.available_copies += 1
        book.save()
        return Response({'status': 'Book returned successfully.'}, status=status.HTTP_200_OK)

class MemberViewSet(viewsets.ModelViewSet):
    queryset = Member.objects.all()
    serializer_class = MemberSerializer

class LoanViewSet(viewsets.ModelViewSet):
    queryset = Loan.objects.all().select_related('book', 'member', 'member__user')
    serializer_class = LoanSerializer

    @action(detail=True, methods=['post'])
    def extend_due_date(self, request, pk=None):
        loan = self.get_object()
        if loan.due_date < timezone.now().date():
            return Response({'error': 'Due date has already passed.'}, status=status.HTTP_400_BAD_REQUEST)
        serializer = ExtendDueDateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        additional_days = serializer.validated_data['additional_days']
        loan.due_date = loan.due_date + timedelta(days=additional_days)
        loan.save()
        return Response(LoanSerializer(loan).data)
  

class ToActiveMembersView(generics.GenericAPIView):
    queryset = Member.objects.all().select_related('user')
    def get(self, request, *args, **kwargs):
        top_members = Member.objects.all().annotate(
            active_loans=Count('loans', filter=Q(loans__is_returned=False))
        ).order_by('-active_loans').select_related('user')[:5]
        for item in top_members:
            print(item)
        # Did not use serializer due to time constraint
        data = []
        for item in top_members:
            data.append({
                'id': item.id,
                'username': item.user.username,
                'email': item.user.email,
                'active_loans': item.active_loans,
            })
        return Response(data)