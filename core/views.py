from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from core.forms import *
from django.contrib import messages
from core.models import *
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
import razorpay
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.core.mail import send_mail
from django.http import HttpResponse
from django.core.paginator import Paginator

razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_ID, settings.RAZORPAY_SECRET))

def index(request):
    products = Product.objects.all()
    paginator = Paginator(products, 9)
    page_number = request.GET.get('page')
    product = paginator.get_page(page_number)
    
    context = {
        'product_list': product,
        'products': products
    }
    return render(request, 'core/index.html', context)

def add_product(request):
    if request.method == 'POST':
        form = ProductForm(request.POST,request.FILES)
        if form.is_valid():
            print("True")
            form.save()
            print("Data added successfully")
            messages.success(request, "Product added successfully")
            return redirect('/')
        else:
            print("Not working")
            print(form.errors)
            messages.info(request, "Product is not added, Try Again!")
            # return redirect('/') 
    else:
        form = ProductForm()
        pass  
    return render(request, 'core/add_product.html', {'form': form})

def product_desc(request, pk):
    product = Product.objects.get(pk=pk)
    return render(request, 'core/product_desc.html', {'product': product})

def add_to_cart(request, pk):
    product = Product.objects.get(pk=pk)
    
    order_item, created = OrderItem.objects.get_or_create(
        product=product,
        user=request.user,
        ordered=False,
    )
    
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]  # Fix: use 'order_qs' instead of 'order'
        if order.items.filter(product__pk=pk).exists():
            order_item.quantity += 1
            order_item.save()
            messages.info(request, "Added quantity item")
            return redirect("product_desc", pk=pk)
        else:
            order.items.add(order_item)
            messages.info(request, "Item added to cart")
            return redirect("product_desc", pk=pk)
    else:
        ordered_date = timezone.now()
        order = Order.objects.create(user=request.user, ordered_date=ordered_date)
        order.items.add(order_item)
        messages.info(request, "Item added to Cart")
        return redirect("product_desc", pk=pk)

def orderlist(request):
    if Order.objects.filter(user=request.user, ordered=False).exists():
        order = Order.objects.get(user=request.user, ordered=False)
        return render(request, 'core/orderlist.html', {'order':order})
    return render(request, 'core/orderlist.html', {'message': "Your Cart is Empty!"})

def add_item(request, pk):
    product = Product.objects.get(pk=pk)
    
    order_item, created = OrderItem.objects.get_or_create(
        product=product,
        user=request.user,
        ordered=False,
    )
    
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]  # Fix: use 'order_qs' instead of 'order'
        if order.items.filter(product__pk=pk).exists():
            if order_item.quantity <= product.product_available_count:
                order_item.quantity += 1
                order_item.save()
                messages.info(request, "Added quantity item")
                return redirect("orderlist")
            else:
                messages.info(request, "Out of Stock!")
                return redirect('orderlist')
        else:
            order.items.add(order_item)
            messages.info(request, "No such item")
            return redirect("orderlist")
    else:
        ordered_date = timezone.now()
        order = Order.objects.create(user=request.user, ordered_date=ordered_date)
        order.items.add(order_item)
        messages.info(request, "Item added to Cart")
        return redirect("orderlist", pk=pk)

def remove_item(request, pk):
    item = get_object_or_404(Product, pk=pk)
    order_qs = Order.objects.filter(
        user = request.user,
        ordered = False,
    )
    
    if order_qs.exists():
        order = order_qs[0]
        if order.items.filter(product__pk=pk).exists():
            order_item = OrderItem.objects.filter(
                product = item,
                user = request.user,
                ordered = False,
            )[0]
            
            if order_item.quantity > 1:
                order_item.quantity -= 1
                order_item.save()
            else:
                order_item.delete()
            
            messages.info(request, "Item quantity was updated")
            return redirect('orderlist')
        else:
            messages.info(request, "This item is not in your cart")
            return redirect('orderlist')
        
    else:
        messages.info(request, "You do not have any Order")
        return redirect('orderlist')
        
        
def checkout_page(request):
    if CheckoutAddress.objects.filter(user=request.user).exists():
        return render(request, 'core/checkout_page.html', {
            'payment_allow': 'allow'
        })
        
    
    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        try:
            if form.is_valid():
                street_address = form.cleaned_data.get('street_address')
                apartment_address = form.cleaned_data.get('apartment_address')
                country = form.cleaned_data.get('country')
                zip_code = form.cleaned_data.get('zip')
                
                checkout_address = CheckoutAddress(user=request.user, street_address=street_address,
                apartment_address=apartment_address,
                country=country,
                zip_code=zip_code)
                
                checkout_address.save()
                print("It should render the summary page")
                return render(request, 'core/checkout_page.html', {
                    'payment_allow': 'allow'
                })
        except Exception as e:
            messages.warning(request, "Failed Checkout")
            return redirect('checkout_page')
    else:
        form = CheckoutForm()
        return render(request, 'core/checkout_page.html', {'form': form})
    

def payment_success(request):

    order = Order.objects.get(user=request.user, ordered=False)
    address = CheckoutAddress.objects.get(user=request.user)
    order_amount = order.get_total_price()
    order_currency = "INR"
    order_receipt = order.order_id
    order_date = order.ordered_date
    notes = {
            "street_address": address.street_address,
            "apartment_address": address.apartment_address,
            "country": address.country.name,
            "zip": address.zip_code,
              
        }
    
    info =  {
        "order": order,
         "orderId": order.order_id,
        "final_price": order_amount,
        "order_currency": order_currency,
        "notes": notes,
        "order_date": order_date,
         "user": request.user,
            "items": order.get_item_names()  ,
            "prices": order.get_total_price()
        
    }
    
    print("order id: ", order.order_id)
    
    item_price = {}
    
    for order_item in order.items.all():
        item_name = order_item.product.name  # Get the product name
        item_price[item_name] = order_item.get_final_price()  # Get the total price for that item and add to the dictionary

    print(item_price)  

    return render(request, "core/invoice.html", {
    "order": order,
    "orderId": order.order_id,
    "final_price": order_amount,
    "order_currency": order_currency,
    "notes": notes,
    "user": request.user,
    "items": order.get_item_names(),  
    "item_price": item_price,
    "order_date": order_date
})

# @csrf_exempt    
# def handle_request(request):
#     print("Inside handle request function")
#     try:
#                 order_db = Order.objects.get(order_id=)
#                 print("Order found")
#     except Order.DoesNotExist:
#                 print("Order not found")
#                 return HttpResponse("Order not found", status=404)
            

#     order_db.save()
#     print("Working.......")
            
#     print("Working final fine....")
#     amount = order_db.get_total_price() * 100 
#     order_db.ordered = True
#     order_db.save()
#     print("Payment success")
#     request.session["order_complete"] = "Your order is successfully placed, you will receive your order within 3 days."
#     return render(request, "core/invoice.html")
    
           
def invoice(request):
    return render(request, "core/invoice.html")