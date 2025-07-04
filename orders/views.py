from django.shortcuts import render,redirect
from .models import Payment,OrderProduct,Order
from store.models import Product
from cart.models import Cartitem
from .forms import Orderform,Order
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import datetime,json
from django.core.mail import EmailMessage
from django.template.loader import render_to_string

# Create your views here.
def place_order(request,total=0, quantity =0):
    current_user = request.user
    #if the cart count is 0 then redirect back to shop
    cart_items = Cartitem.objects.filter(user=current_user)
    cart_count = cart_items.count()
    if cart_count <= 0:
        return redirect('store')
    
    grand_total = 0
    tax = 0
    for cart_item in cart_items:
        total+= (cart_item.product.price * cart_item.quantity)
        quantity += cart_item.quantity

    tax = (2*total)/100
    grand_total= tax+total
    
    if request.method == 'POST':
        form = Orderform(request.POST)

        if form.is_valid():
            #store all the billing information inside order table
            data = Order()
            data.user = current_user
            data.first_name = form.cleaned_data['first_name']
            data.last_name = form.cleaned_data['last_name']
            data.phone = form.cleaned_data['phone']
            data.email = form.cleaned_data['email']
            data.address_line_1 = form.cleaned_data['address_line_1']
            data.address_line_2 = form.cleaned_data['address_line_2']
            data.country = form.cleaned_data['country']
            data.state = form.cleaned_data['state']
            data.city = form.cleaned_data['city']
            data.order_note = form.cleaned_data['order_note']
            data.order_total = grand_total
            data.tax = tax
            data.ip = request.META.get('REMOTE_ADDR')
            data.save()
            #geenrate order nno:
            yr = int(datetime.date.today().strftime('%Y'))
            dt = int(datetime.date.today().strftime('%d'))
            mt = int(datetime.date.today().strftime('%m'))
            d = datetime.date(yr,mt,dt)
            current_date = d.strftime("%Y%m%d")
            order_number = current_date+ str(data.id)
            data.order_number = order_number
            data.save()
            order = Order.objects.get(user=current_user, is_ordered = False, order_number = order_number)
            context={
                'order':order,
                'cart_items':cart_items,
                'total':total,
                'tax':tax,
                'grand_total':grand_total,

            }
            return render(request,'payment.html',context)
    else:
        return redirect('checkout')  

def payments(request):
    body = json.loads(request.body)
    order = Order.objects.get(user = request.user, is_ordered = False, order_number = body['orderID'])
    print("✅ Received:", body)
    payment = Payment(
        user = request.user,
        payment_id = body['transaction_ID'],
        payment_method = body['payment_method'],
        amount_paid = order.order_total,
        status = body['status'],
    )
    payment.save()
    order.payment = payment
    order.is_ordered = True
    order.save()

     #move the cart items to the order product tabel
    cart_items = Cartitem.objects.filter(user=request.user)
    for item in cart_items:
        orderproduct = OrderProduct()
        orderproduct.order_id = order.id
        orderproduct.payment = payment
        orderproduct.user_id = request.user.id
        orderproduct.product_id = item.product_id
        orderproduct.quantity = item.quantity
        orderproduct.product_price = item.product.price
        orderproduct.ordered = True
        orderproduct.save()

        cart_item = Cartitem.objects.get(id=item.id)
        product_variation = cart_item.variations.all()
        orderproduct = OrderProduct.objects.get(id = orderproduct.id)
        orderproduct.variations.set(product_variation)
        orderproduct.save()
        #reduce the quantity of sold products
        product =   Product.objects.get(id = item.product_id)
        product.stock -= item.quantity
        product.save()

    #clear the cart
    Cartitem.objects.filter(user=request.user).delete()

    #sent email to customer  for orderrecieved
    mail_subject = 'Thank you for your for your order'
    message = render_to_string('order_recieved_email.html',{
        'user': request.user,
        'order':order,
    }) 
    to_email = request.user.email
    send_email = EmailMessage(mail_subject, message, to=[to_email])
    send_email.send()

    #send order number and transaction id back to senddata method via JsonPesponse
    data = {
    'order_number' : order.order_number,
    'transaction_ID' : payment.payment_id
    }
    return JsonResponse(data)

def order_complete(request):
    order_number = request.GET.get('order_number')
    transaction_ID = request.GET.get('payment_id')
    try:
        order = Order.objects.get(order_number=order_number, is_ordered = True)
        order_products = OrderProduct.objects.filter(order_id = order.id)
        subtotal = 0
        for i in order_products:
            subtotal += i.product_price * i.quantity

        payment = Payment.objects.get(payment_id=transaction_ID)    
        context={
            'order':order,
            'ordered_products':order_products,
            'order_number': order.order_number,
            'transID': payment.payment_id,
            'payment':payment,
            'subtotal': subtotal,
        }
        return render(request,'order_complete.html',context)
    except(Payment.DoesNotExist,Order.DoesNotExist):
        return redirect('index')