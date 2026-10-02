from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages

def iniciar_sesion(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, f'¡Bienvenido {user.username}!')
            return redirect('usuarios:tablero')  
        else:
            messages.error(request, 'Usuario o contraseña incorrectos')
    
    return render(request, 'usuarios/login.html')  
@login_required
def cerrar_sesion(request):
    logout(request)
    messages.success(request, 'Sesión cerrada correctamente')
    return redirect('usuarios:iniciar_sesion')  

@login_required
def tablero(request):
    return render(request, 'usuarios/tablero.html') 