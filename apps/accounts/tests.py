from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch
from apps.accounts.models import PasswordResetToken
from apps.accounts.models import User, CustomerProfile, PhoneOTP, UserSession

class CustomerAuthTests(TestCase):

    def setUp(self):
        """Har test se pehle setup run hota hai."""
        self.client = APIClient()
        self.phone = "+919876543210"
        self.invalid_phone = "12345"
        self.valid_otp = "123456"
        self.invalid_otp = "654321"

    @patch('apps.accounts.tasks.send_sms_task.delay')  # Hamare SMS task ko mock (disable) kar rahe hain
    def test_1_customer_request_otp_new_user(self, mock_send_sms):
        """Test: Naya customer jab OTP request karta hai."""
        
        # Check: Shuruaat mein koi user nahi hona chahiye
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(CustomerProfile.objects.count(), 0)
        
        # API call karein
        url = "/api/v1/auth/customer/request-otp/"
        response = self.client.post(url, {"phone": self.phone})
        
        # Check: Response successful hona chahiye
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check: Ek naya User aur CustomerProfile ban gaya ho
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(CustomerProfile.objects.count(), 1)
        
        # Check: User ka phone number sahi set hua ho
        user = User.objects.first()
        self.assertEqual(user.phone, self.phone)
        
        # Check: Ek OTP record ban gaya ho
        self.assertEqual(PhoneOTP.objects.count(), 1)
        
        # Check: SMS task call hua ho (mocked)
        mock_send_sms.assert_called_once()

    def test_2_customer_verify_otp_valid(self):
        """Test: Sahi OTP se login successful hona chahiye."""
        
        # Setup: Pehle ek user aur valid OTP banate hain
        user = User.objects.create(phone=self.phone, is_customer=True)
        CustomerProfile.objects.create(user=user)
        otp_obj = PhoneOTP.create_otp(
            phone=self.phone, 
            login_type="CUSTOMER", 
            code=self.valid_otp
        )
        
        # API call karein
        url = "/api/v1/auth/customer/verify-otp/"
        data = {"phone": self.phone, "otp": self.valid_otp}
        response = self.client.post(url, data)
        
        # Check: Response successful (200 OK) hona chahiye
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check: Response mein tokens milne chahiye
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        
        # Check: OTP 'is_used' mark ho gaya ho
        otp_obj.refresh_from_db()
        self.assertTrue(otp_obj.is_used)
        
        # Check: Ek UserSession record ban gaya ho
        self.assertTrue(UserSession.objects.filter(user=user, role="CUSTOMER").exists())

    def test_3_customer_verify_otp_invalid(self):
        """Test: Galat OTP se login fail hona chahiye."""
        
        # Setup: Pehle ek user aur valid OTP banate hain
        user = User.objects.create(phone=self.phone, is_customer=True)
        otp_obj = PhoneOTP.create_otp(
            phone=self.phone, 
            login_type="CUSTOMER", 
            code=self.valid_otp
        )
        
        # API call karein (galat OTP ke saath)
        url = "/api/v1/auth/customer/verify-otp/"
        data = {"phone": self.phone, "otp": self.invalid_otp}
        response = self.client.post(url, data)
        
        # Check: Response 400 Bad Request hona chahiye
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Check: Response mein error detail hona chahiye
        self.assertIn("detail", response.data)
        self.assertEqual(response.data['detail'], "Invalid OTP")
        
        # Check: OTP 'is_used' mark NAHI hona chahiye
        otp_obj.refresh_from_db()
        self.assertFalse(otp_obj.is_used)
        
        # Check: OTP attempts badh gaye honge
        self.assertEqual(otp_obj.attempts, 1)
        
        # Check: Koi UserSession nahi banna chahiye
        self.assertFalse(UserSession.objects.filter(user=user).exists())




class AdminPasswordResetTests(TestCase):
    
    def setUp(self):
        self.client = APIClient()
        self.admin_phone = "+919999988888"
        self.admin_email = "admin@quickdash.com"
        self.admin_pass = "StrongPassword123"
        
        # Ek Admin user banayein (jiske paas password hai)
        self.admin_user = User.objects.create_superuser(
            phone=self.admin_phone,
            password=self.admin_pass
        )
        self.admin_user.email = self.admin_email
        self.admin_user.full_name = "Admin User"
        self.admin_user.save()

    @patch('apps.accounts.tasks.send_admin_password_reset_email_task.delay')
    def test_1_admin_forgot_password_success(self, mock_send_email):
        """Test: Admin forgot password request (email se)."""
        
        url = "/api/v1/auth/admin/forgot-password/"
        response = self.client.post(url, {"identifier": self.admin_email})
        
        # Check: Response 200 hona chahiye
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check: Ek naya PasswordResetToken ban gaya ho
        self.assertTrue(PasswordResetToken.objects.filter(user=self.admin_user).exists())
        
        # Check: Email task call hua ho
        mock_send_email.assert_called_once()

    @patch('apps.accounts.tasks.send_admin_password_reset_email_task.delay')
    def test_2_admin_forgot_password_no_email_user(self, mock_send_email):
        """Test: Agar admin user ka email set nahi hai."""
        
        self.admin_user.email = "" # Email hata dein
        self.admin_user.save()
        
        url = "/api/v1/auth/admin/forgot-password/"
        response = self.client.post(url, {"identifier": self.admin_phone})
        
        # Check: Response 400 hona chahiye
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("does not have an email", response.data['detail'])
        
        # Check: Koi email task call na hua ho
        mock_send_email.assert_not_called()

    def test_3_admin_reset_password_success(self):
        """Test: Sahi token se password reset karna."""
        
        # 1. Ek valid token banayein
        token_obj = PasswordResetToken.create_token(user=self.admin_user)
        token_value = str(token_obj.token)
        new_pass = "NewStrongPass!@#"
        
        # 2. Reset API call karein
        url = "/api/v1/auth/admin/reset-password/"
        data = {"token": token_value, "new_password": new_pass}
        response = self.client.post(url, data)
        
        # Check: Response 200 OK hona chahiye
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("Password has been reset", response.data['detail'])
        
        # Check: Token 'is_used' mark ho gaya ho
        token_obj.refresh_from_db()
        self.assertTrue(token_obj.is_used)
        
        # Check: Naya password set hua ho (login karke check karein)
        self.admin_user.refresh_from_db()
        self.assertTrue(self.admin_user.check_password(new_pass))
        
        # Check: Purana password ab kaam nahi karna chahiye
        self.assertFalse(self.admin_user.check_password(self.admin_pass))

    def test_4_admin_reset_password_invalid_token(self):
        """Test: Galat token se password reset fail hona chahiye."""
        
        url = "/api/v1/auth/admin/reset-password/"
        data = {"token": "invalid-token-123", "new_password": "some-pass"}
        response = self.client.post(url, data)
        
        # Check: Response 400 Bad Request hona chahiye
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Invalid or expired token", response.data['detail'])