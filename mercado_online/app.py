import os
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'clave_secreta_super_segura_123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mercado.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'webp'}

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Asegurar que exista la carpeta de subida de imágenes
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# ==================== MODELOS DE BASE DE DATOS ====================
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    es_admin = db.Column(db.Boolean, default=False)  # True = Vendedor/Admin, False = Cliente
    productos = db.relationship('Product', backref='vendedor', lazy=True)
    pedidos = db.relationship('Order', backref='comprador', lazy=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text, nullable=False)
    precio = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, nullable=False)
    categoria = db.Column(db.String(50), nullable=False)
    imagen = db.Column(db.String(200), default='default.png')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reviews = db.relationship('Review', backref='producto', cascade="all, delete-orphan", lazy=True)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    total = db.Column(db.Float, nullable=False)
    estado = db.Column(db.String(50), default='Pendiente de Pago')
    fecha = db.Column(db.DateTime, server_default=db.func.now())
    items = db.relationship('OrderItem', backref='pedido', cascade="all, delete-orphan", lazy=True)

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    precio_unitario = db.Column(db.Float, nullable=False)
    producto = db.relationship('Product')

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    calificacion = db.Column(db.Integer, nullable=False) # 1 a 5 estrellas
    comentario = db.Column(db.Text, nullable=False)
    usuario = db.relationship('User')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ==================== RUTAS Y CONTROLADORES ====================

@app.route('/')
def index():
    busqueda = request.args.get('q', '')
    categoria = request.args.get('categoria', '')
    
    query = Product.query
    if busqueda:
        query = query.filter(Product.nombre.ilike(f'%{busqueda}%'))
    if categoria:
        query = query.filter_by(categoria=categoria)
        
    productos = query.all()
    categorias = db.session.query(Product.categoria).distinct().all()
    categorias = [c[0] for c in categorias]
    return render_template('index.html', productos=productos, categorias=categorias, busqueda=busqueda, categoria_act=categoria)

@app.route('/producto/<int:id>', methods=['GET', 'POST'])
def detalle_producto(id):
    producto = Product.query.get_or_404(id)
    if request.method == 'POST' and current_user.is_authenticated:
        if current_user.es_admin:
            flash('Los administradores no pueden dejar reseñas.', 'warning')
            return redirect(url_for('detalle_producto', id=id))
        
        calificacion = int(request.form.get('calificacion'))
        comentario = request.form.get('comentario')
        
        nueva_review = Review(product_id=producto.id, user_id=current_user.id, calificacion=calificacion, comentario=comentario)
        db.session.add(nueva_review)
        db.session.commit()
        flash('¡Reseña publicada con éxito!', 'success')
        return redirect(url_for('detalle_producto', id=id))
        
    return render_template('producto.html', producto=producto)

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        email = request.form.get('email')
        password = request.form.get('password')
        es_admin = True if request.form.get('es_admin') == 'on' else False
        
        usuario_existente = User.query.filter_by(email=email).first()
        if usuario_existente:
            flash('El correo electrónico ya está registrado.', 'danger')
            return redirect(url_for('registro'))
            
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        nuevo_usuario = User(nombre=nombre, email=email, password=hashed_password, es_admin=es_admin)
        db.session.add(nuevo_usuario)
        db.session.commit()
        
        flash('¡Cuenta creada con éxito! Ahora puedes iniciar sesión.', 'success')
        return redirect(url_for('login'))
    return render_template('registro.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        usuario = User.query.filter_by(email=email).first()
        
        if usuario and check_password_hash(usuario.password, password):
            login_user(usuario)
            flash(f'¡Bienvenido de nuevo, {usuario.nombre}!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Correo o contraseña incorrectos.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Has cerrado sesión correctamente.', 'info')
    return redirect(url_for('index'))

# --- CARRITO DE COMPRAS (Manejado por Sesión) ---
@app.route('/carrito')
def ver_carrito():
    carrito = request.cookies.get('carrito', '{}')
    import json
    carrito_dict = json.loads(carrito)
    
    items = []
    total = 0
    for prod_id, cantidad in carrito_dict.items():
        producto = Product.query.get(int(prod_id))
        if producto:
            subtotal = producto.precio * cantidad
            total += subtotal
            items.append({'producto': producto, 'cantidad': cantidad, 'subtotal': subtotal})
            
    return render_template('carrito.html', items=items, total=total)

@app.route('/carrito/agregar/<int:id>', methods=['POST'])
def agregar_carrito(id):
    import json
    cantidad = int(request.form.get('cantidad', 1))
    carrito = request.cookies.get('carrito', '{}')
    carrito_dict = json.loads(carrito)
    
    if str(id) in carrito_dict:
        carrito_dict[str(id)] += cantidad
    else:
        carrito_dict[str(id)] = cantidad
        
    resp = redirect(url_for('ver_carrito'))
    resp.set_cookie('carrito', json.dumps(carrito_dict))
    flash('Producto añadido al carrito.', 'success')
    return resp

@app.route('/carrito/remover/<int:id>')
def remover_carrito(id):
    import json
    carrito = request.cookies.get('carrito', '{}')
    carrito_dict = json.loads(carrito)
    
    if str(id) in carrito_dict:
        del carrito_dict[str(id)]
        
    resp = redirect(url_for('ver_carrito'))
    resp.set_cookie('carrito', json.dumps(carrito_dict))
    flash('Producto removido del carrito.', 'info')
    return resp

# --- CHECKOUT Y PAGOS ---
@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    import json
    if current_user.es_admin:
        flash('Los administradores no pueden realizar compras.', 'warning')
        return redirect(url_for('index'))
        
    carrito = request.cookies.get('carrito', '{}')
    carrito_dict = json.loads(carrito)
    if not carrito_dict:
        flash('Tu carrito está vacío.', 'warning')
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        total_pedido = 0
        items_pedido = []
        
        for prod_id, cantidad in carrito_dict.items():
            producto = Product.query.get(int(prod_id))
            if producto and producto.stock >= cantidad:
                total_pedido += producto.precio * cantidad
                producto.stock -= cantidad
                items_pedido.append((producto, cantidad))
            else:
                flash(f'Stock insuficiente para el producto.', 'danger')
                return redirect(url_for('ver_carrito'))
                
        nuevo_pedido = Order(user_id=current_user.id, total=total_pedido, estado='Pagado y Procesando')
        db.session.add(nuevo_pedido)
        db.session.flush() # Para obtener el ID del pedido
        
        for producto, cantidad in items_pedido:
            item = OrderItem(order_id=nuevo_pedido.id, product_id=producto.id, cantidad=cantidad, precio_unitario=producto.precio)
            db.session.add(item)
            
        db.session.commit()
        
        # Limpiar carrito
        resp = redirect(url_for('mis_pedidos'))
        resp.set_cookie('carrito', '', expires=0)
        flash('¡Pago simulado con éxito! Pedido creado correctamente.', 'success')
        return resp
        
    total = sum(Product.query.get(int(pid)).precio * cant for pid, cant in carrito_dict.items() if Product.query.get(int(pid)))
    return render_template('checkout.html', total=total)

@app.route('/mis-pedidos')
@login_required
def mis_pedidos():
    pedidos = Order.query.filter_by(user_id=current_user.id).order_by(Order.fecha.desc()).all()
    return render_template('mis_pedidos.html', pedidos=pedidos)

# --- PANEL DE ADMINISTRACIÓN / VENDEDOR ---
@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    if not current_user.es_admin:
        flash('Acceso denegado. Solo para vendedores/administradores.', 'danger')
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        descripcion = request.form.get('descripcion')
        precio = float(request.form.get('precio'))
        stock = int(request.form.get('stock'))
        categoria = request.form.get('categoria')
        
        file = request.files.get('imagen')
        filename = 'default.png'
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            
        nuevo_prod = Product(nombre=nombre, descripcion=descripcion, precio=precio, stock=stock, categoria=categoria, imagen=filename, user_id=current_user.id)
        db.session.add(nuevo_prod)
        db.session.commit()
        flash('Producto agregado exitosamente al mercado.', 'success')
        return redirect(url_for('admin'))
        
    productos = Product.query.filter_by(user_id=current_user.id).all()
    return render_template('admin.html', productos=productos)

@app.route('/admin/producto/eliminar/<int:id>')
@login_required
def eliminar_producto(id):
    producto = Product.query.get_or_404(id)
    if producto.user_id != current_user.id and not current_user.es_admin:
        flash('No tienes permisos para eliminar este producto.', 'danger')
        return redirect(url_for('admin'))
        
    db.session.delete(producto)
    db.session.commit()
    flash('Producto eliminado.', 'info')
    return redirect(url_for('admin'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)