from django.shortcuts import render,redirect,HttpResponse
from django.contrib import messages,auth
from django.contrib.auth.decorators import login_required
from .forms import Registrationform
from .models import Account
from django.views.decorators.csrf import csrf_protect
from django.urls import reverse
from cart.models import Cart,Cartitem
from cart.views import _cart_id
import requests
#verification email
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode , urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMessage

# Create your views here.
@csrf_protect
def register(request):
    if request.method == "POST":
        form = Registrationform(request.POST)
        if form.is_valid():
            first_name = form.cleaned_data['first_name']
            last_name = form.cleaned_data['last_name']
            email = form.cleaned_data['email']
            phone_no = form.cleaned_data['phone_no']
            password = form.cleaned_data['password']
            username = email.split("@")[0]

            user = Account.objects.create_user(first_name= first_name, last_name=last_name, username = username, email=email, password=password)
            user.phone_no = phone_no
            #user.is_active = True
            user.save()
            #user activation
            current_site = get_current_site(request)
            mail_subject = 'please activate your account'
            message = render_to_string('account_verfication.html',{
                'user': user,
                'domain' : current_site,
                'uid' : urlsafe_base64_encode(force_bytes(user.pk)),
                'token' : default_token_generator.make_token(user)
            }) 
            to_email = email
            send_email = EmailMessage(mail_subject, message, to=[to_email])
            send_email.send()
            login_url = reverse('login')
            redirect_url = f"{login_url}?command=verification&email={email}"
            return redirect(redirect_url)

          #  messages.success(request, 'Thank you for registeration. We have sent you an email pleaase verify it')
          #  return redirect('login/?command=verification='+email)
    else:        
        form = Registrationform()
    context = {
         'form':form,
        }
    return render(request, 'register.html', context)

@csrf_protect
def login(request):
    if request.method == "POST":
        email = request.POST['email']
        password = request.POST['password']

        user =auth.authenticate(email = email, password = password)

        if user is not None:
            try:
                cart= Cart.objects.get(cart_id=_cart_id(request))
                is_cart_item_exists = Cartitem.objects.filter(cart=cart).exists()
                if is_cart_item_exists:
                    cart_item = Cartitem.objects.filter(cart=cart)
#getting the product variations by cart id
                    product_variation = []
                    for item in cart_item:
                        variation = item.variations.all()
                        product_variation.append(list(variation))

                    #get the cart  items from the user to access its product variation
                    cart_item= Cartitem.objects.filter(user=user)
                    ex_var_list =[]
                    id=[]
                    for item in cart_item:
                        existing_variation = item.variations.all()
                        ex_var_list.append(list(existing_variation))
                        id.append(item.id)

                    for pr in product_variation:
                        if pr in ex_var_list:
                            index = ex_var_list.index(pr)
                            item_id = id[index]
                            item = Cartitem.objects.get(id=item_id)
                            item.quantity += 1
                            item.user = user
                            item.save()    

                        else:
                            cart_item = Cartitem.objects.filter(cart = cart)
                            for item in cart_item:
                                item.user = user
                                item.save()
            except:
                pass

            auth.login(request, user)
            messages.success(request,"You are logged in")
            url = request.META.get('HTTP_REFERER')
            try:
                query = requests.utils.urlparse(url).query
                #print("query ->",query)
                #next=/cart/checkout/
                params = dict(x.split('=') for x in query.split('&'))
               # print('params ->',params)
                if 'next' in params:
                    nextpage = params['next']
                    return redirect(nextpage)
            except:
                return redirect('dashboard')
        else:
            messages.error(request,"Invalid login credentials")
            return redirect('login')
    return render(request, 'login.html')


@login_required(login_url = 'login')
def logout(request):
    auth.logout(request)
    messages.success(request, 'you are loggeg out')
    return redirect('login')


def activate(request , uidb64 , token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = Account._default_manager.get(pk=uid)
    except(TypeError, ValueError , OverflowError, Account.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        messages.success(request, 'Congratulations ypur account is activated')
        return redirect('login')
    else:
        messages.error(request, "Invalid activate link")
        return redirect('register')

@login_required(login_url = 'login')
def dashboard(request):
    return render(request,'dashboard.html')

def forgotpassword(request):
    if request.method == 'POST':
        email = request.POST['email']
        if Account.objects.filter(email=email).exist():
            user = Account.objects.get(email__exact=email)

            #reset password email
            current_site = get_current_site(request)
            mail_subject = 'Reset your password'
            message = render_to_string('reset_password_email.html',{
                'user': user,
                'domain' : current_site,
                'uid' : urlsafe_base64_encode(force_bytes(user.pk)),
                'token' : default_token_generator.make_token(user)
            }) 
            to_email = email
            send_email = EmailMessage(mail_subject, message, to=[to_email])
            send_email.send()
            messages.success(request,'reset password email has been sent to your email address')
            return redirect('login')
        else:
            messages.error(request, 'Account does not exist')
            return redirect('forgotpassword')
    return render(request,"forgotpassword.html")

def reset_password_validate(request, uidb64 , token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = Account._default_manager.get(pk=uid)
    except(TypeError, ValueError , OverflowError, Account.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        request.session['uid'] = uid
        messages.success(request, 'Please reset your passsword')
        return redirect('resetpassword')
    else:
        messages.error(request,'This link has been expired')
        return redirect(request,'login')
    
def resetpassword(request):
    if request.method == 'POST':
        password = request.POST['password']
        confirmpassword = request.POST['confirmpassword']

        if password == confirmpassword:
            uid = request.session.get['uid']
            user = Account.objects.get(pk=uid)
            user.set_password(password)
            user.save()
            messages.success(request,'password reset successfull')
            return redirect('login')

        else:
            messages(request,'Password does not match')
            return redirect('resetpassword')
    else:    
        return render(request,'resetpassword.html')            