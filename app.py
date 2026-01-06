import os
from flask import Flask, request, redirect, session, make_response, render_template_string
from datetime import datetime
import sqlite3
import csv
import io
from fpdf import FPDF
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'super_secreto_laboratorio')

# --- CONFIGURACIÓN BASE DE DATOS ---
# En Render, usaremos un archivo local por ahora.
# OJO: En la versión gratuita de Render, si la app se reinicia, este archivo se borra.
# Para producción real, más adelante conectaremos una base de datos PostgreSQL externa.
DB_PATH = 'laboratorio_politico.db'

# --- SEGURIDAD ---
PASSWORD_HASH = generate_password_hash("admin123")

# --- HTML HEADER & FOOTER ---
HTML_HEAD = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1" />
  <title>Reserva Lab - Ciencia Política</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      theme: { 
        extend: { 
            fontFamily: { sans: ["Inter","sans-serif"] },
            colors: { uagrm: { 700: '#004c8c', 800: '#003366' } } 
        } 
      }
    }
  </script>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
</head>
<body class="bg-slate-50 text-slate-800 font-sans leading-relaxed">
  <div class="h-1.5 w-full bg-gradient-to-r from-red-700 via-yellow-500 to-green-700"></div>
  <header class="sticky top-0 z-30 bg-white/95 backdrop-blur border-b border-slate-200 shadow-sm">
    <div class="max-w-7xl mx-auto px-4 py-3 flex flex-wrap items-center justify-between gap-3">
      <a href="/reservalab" class="flex items-center gap-3">
        <img src="https://i.imgur.com/ldeXZmG.png" alt="Logo" class="h-10 w-10 object-contain" />
        <div class="leading-tight">
          <p class="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">UAGRM</p>
          <h1 class="font-bold text-sm sm:text-base text-slate-900 leading-tight">Ciencia Política y<br>Administración Pública</h1>
        </div>
      </a>
      <nav class="flex items-center gap-4 text-sm font-medium ml-auto">
        <a href="/reservalab" class="hover:text-uagrm-700 transition">Inicio</a>
        {% if session.get('admin_logueado') %}
            <a href="/admin" class="text-emerald-700 font-bold">Admin</a>
            <a href="/logout" class="text-rose-600">Salir</a>
        {% else %}
            <a href="/login" class="text-slate-500 hover:text-uagrm-700 transition">Director</a>
        {% endif %}
      </nav>
    </div>
  </header>
  <main class="min-h-screen pb-12">
"""

HTML_FOOTER = """
  </main>
  <footer class="border-t border-slate-200 bg-white py-8 text-center text-sm text-slate-500">
    <p>© 2026 Carrera de Ciencia Política y Administración Pública — UAGRM.</p>
  </footer>
</body>
</html>
"""

# --- BASE DE DATOS ---
def inicializar_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reservas_laboratorio (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                registro TEXT NOT NULL,
                ci TEXT NOT NULL,
                celular TEXT NOT NULL,
                email TEXT NOT NULL,
                responsable_actividad TEXT,
                tipo_actividad TEXT NOT NULL,
                objetivo TEXT NOT NULL,
                fecha TEXT NOT NULL,
                hora_inicio TEXT NOT NULL,
                hora_fin TEXT NOT NULL,
                participantes INTEGER NOT NULL,
                estado TEXT DEFAULT 'Pendiente'
            )
        ''')
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error DB: {e}")

# Inicializamos al arrancar
inicializar_db()

# --- LÓGICA ---
def hay_cruce_de_horario(fecha, inicio, fin):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM reservas_laboratorio WHERE fecha = ? AND (hora_inicio < ? AND hora_fin > ?) AND estado != "Rechazada"', (fecha, fin, inicio))
    res = cursor.fetchone()
    conn.close()
    return res is not None

# --- PDF ---
class PDF(FPDF): pass
def crear_carta_pdf(datos):
    pdf = PDF()
    pdf.add_page(); pdf.set_margins(25, 25, 25)
    def txt(t): return t.encode('latin-1', 'replace').decode('latin-1')
    
    fecha_actual = datetime.now().strftime("%d de %B de %Y")
    meses = {"January":"Enero","February":"Febrero","March":"Marzo","April":"Abril","May":"Mayo","June":"Junio","July":"Julio","August":"Agosto","September":"Septiembre","October":"Octubre","November":"Noviembre","December":"Diciembre"}
    for en, es in meses.items(): fecha_actual = fecha_actual.replace(en, es)

    pdf.set_font('Arial', '', 11)
    pdf.cell(0, 10, txt(f"Santa Cruz de la Sierra, {fecha_actual}"), 0, 1, 'R'); pdf.ln(5)
    
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 5, txt("Señor:"), 0, 1)
    pdf.cell(0, 5, txt("M.Sc. Odin Rodriguez Mercado"), 0, 1)
    pdf.set_font('Arial', '', 11)
    pdf.cell(0, 5, txt("DIRECTOR DE CARRERA"), 0, 1)
    pdf.cell(0, 5, txt("CIENCIA POLÍTICA Y ADM. PÚBLICA - UAGRM"), 0, 1)
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 5, txt("Presente.-"), 0, 1); pdf.ln(10)
    
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, txt("Ref.: SOLICITUD DE USO DE LABORATORIO"), 0, 1, 'R'); pdf.ln(5)
    pdf.set_font('Arial', '', 12)
    cuerpo = f"""De mi mayor consideración:

Mediante la presente, yo, {datos['nombre']}, con Registro Universitario N° {datos['registro']} y C.I. {datos['ci']}, solicito a su autoridad la autorización para el uso del Laboratorio de Análisis Político.

La actividad a realizar es "{datos['tipo_actividad']}" con el siguiente propósito: {datos['objetivo']}.

Detalles:
- Fecha: {datos['fecha']}
- Horario: De {datos['hora_inicio']} a {datos['hora_fin']}
- Participantes: {datos['participantes']}

Me comprometo a hacer un uso responsable de los equipos e instalaciones.

Sin otro particular, me despido atentamente."""
    pdf.multi_cell(0, 7, txt(cuerpo)); pdf.ln(30)
    
    pdf.set_font('Arial', '', 11)
    pdf.cell(0, 5, "____________________________________", 0, 1, 'C')
    pdf.cell(0, 5, txt(datos['nombre']), 0, 1, 'C')
    pdf.cell(0, 5, txt(f"C.I.: {datos['ci']}"), 0, 1, 'C')
    return pdf.output(dest='S').encode('latin-1')

# --- RUTAS ---
@app.route('/')
def home_redirect():
    return redirect('/reservalab')

@app.route('/reservalab')
def index():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, nombre, tipo_actividad, fecha, hora_inicio, hora_fin, estado FROM reservas_laboratorio WHERE estado != "Rechazada" ORDER BY fecha DESC, hora_inicio ASC')
    reservas = cursor.fetchall()
    conn.close()

    content = """
    <div class="max-w-6xl mx-auto px-4 sm:px-6 pt-8">
        <div class="bg-white rounded-2xl p-6 sm:p-8 shadow-sm border border-slate-200 mb-8">
            <h2 class="text-2xl sm:text-3xl font-extrabold text-slate-900 text-center mb-6">
                Formulario de solicitud del Laboratorio de Análisis Político
            </h2>
            <div class="text-sm text-slate-600 space-y-3 bg-slate-50 p-5 rounded-xl border border-slate-100 text-justify">
                <p><strong>Este formulario tiene como finalidad gestionar y autorizar el uso de las instalaciones y recursos tecnológicos.</strong></p>
                <ul class="list-disc pl-5 space-y-1">
                    <li>Solicitar con <span class="text-rose-600 font-bold">72 horas de anticipación</span>.</li>
                    <li>Sujeto a aprobación de la Dirección de Carrera.</li>
                </ul>
            </div>
        </div>

        <div class="grid lg:grid-cols-12 gap-8">
            <div class="lg:col-span-7">
                <div class="bg-white rounded-2xl shadow-lg border border-slate-200 overflow-hidden">
                    <div class="bg-slate-900 px-6 py-4"><h3 class="text-white font-bold text-lg">Información Requerida</h3></div>
                    <form action="/reservar" method="POST" class="p-6 space-y-5">
                        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            <div class="col-span-1 sm:col-span-2"><label class="lbl">Nombre Completo</label><input type="text" name="nombre" required class="inp"></div>
                            <div><label class="lbl">Registro</label><input type="text" name="registro" required class="inp"></div>
                            <div><label class="lbl">C.I.</label><input type="text" name="ci" required class="inp"></div>
                            <div><label class="lbl">Celular</label><input type="tel" name="celular" required class="inp"></div>
                            <div><label class="lbl">Correo</label><input type="email" name="email" required class="inp"></div>
                        </div>
                        <div class="border-t border-slate-100 pt-4 space-y-4">
                            <div><label class="lbl">Responsable (si es distinto)</label><input type="text" name="responsable_actividad" placeholder="Opcional" class="inp"></div>
                            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                <div>
                                    <label class="lbl">Tipo de actividad</label>
                                    <select name="tipo_actividad" class="inp">
                                        <option value="" disabled selected>Seleccione...</option>
                                        <option>Clase Regular</option>
                                        <option>Conferencia</option>
                                        <option>Seminario</option>
                                        <option>Taller</option>
                                        <option>Curso / Capacitación</option>
                                        <option>Consejo de Carrera</option>
                                        <option>Defensa de Tesis / Grado</option>
                                        <option>Entrevista</option>
                                        <option>Grabación de Video</option>
                                        <option>Podcast</option>
                                        <option>Reunión de Investigación</option>
                                        <option>Debate / Simulación</option>
                                        <option>Otro</option>
                                    </select>
                                </div>
                                <div><label class="lbl">Participantes</label><input type="number" name="participantes" required class="inp"></div>
                            </div>
                            <div><label class="lbl">Objetivo / Propósito</label><textarea name="objetivo" rows="2" required class="inp"></textarea></div>
                        </div>
                        <div class="bg-indigo-50 p-4 rounded-xl border border-indigo-100">
                            <label class="lbl text-indigo-800">Fecha y Horario</label>
                            <input type="date" name="fecha" required class="inp mb-2 border-indigo-200">
                            <div class="flex gap-2">
                                <input type="time" name="inicio" required class="inp border-indigo-200"><span class="self-center font-bold text-indigo-400">a</span><input type="time" name="fin" required class="inp border-indigo-200">
                            </div>
                        </div>
                        <div class="flex gap-3 pt-2">
                            <input type="checkbox" required id="c" class="mt-1"><label for="c" class="text-xs text-slate-600">Me comprometo a hacer un uso responsable de los equipos.</label>
                        </div>
                        <button type="submit" class="w-full py-3.5 bg-slate-900 text-white font-bold rounded-xl shadow-lg hover:bg-slate-800 transition">Enviar Solicitud</button>
                    </form>
                </div>
            </div>

            <div class="lg:col-span-5">
                <div class="bg-white rounded-2xl shadow-md border border-slate-200 overflow-hidden sticky top-24">
                    <div class="px-6 py-4 border-b border-slate-100 bg-slate-50"><h3 class="font-bold text-slate-800">Calendario de Ocupación</h3></div>
                    <div class="overflow-x-auto">
                        <table class="min-w-full text-left text-xs sm:text-sm">
                            <thead class="bg-slate-50 text-slate-500 uppercase font-bold"><tr><th class="px-4 py-3">Actividad</th><th class="px-4 py-3">Fecha</th><th class="px-4 py-3">Carta</th></tr></thead>
                            <tbody class="divide-y divide-slate-100">
                                {% for r in reservas %}
                                <tr class="hover:bg-slate-50 transition">
                                    <td class="px-4 py-3">
                                        <p class="font-bold text-slate-900 truncate max-w-[120px]">{{ r[2] }}</p>
                                        <p class="text-xs text-slate-500">{{ r[1] }}</p>
                                        <span class="px-2 py-0.5 rounded-full text-[10px] font-bold {{ 'bg-amber-100 text-amber-700' if r[6]=='Pendiente' else 'bg-emerald-100 text-emerald-700' }}">{{ r[6] }}</span>
                                    </td>
                                    <td class="px-4 py-3 text-slate-600 whitespace-nowrap">{{ r[3] }}<br>{{ r[4] }} - {{ r[5] }}</td>
                                    <td class="px-4 py-3"><a href="/descargar_carta/{{ r[0] }}" class="w-8 h-8 flex items-center justify-center rounded-full bg-slate-100 hover:bg-slate-200">📄</a></td>
                                </tr>
                                {% else %}<tr><td colspan="3" class="px-4 py-8 text-center text-slate-400">Sin reservas.</td></tr>{% endfor %}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <style>.lbl{display:block; font-size:0.75rem; font-weight:700; color:#64748b; text-transform:uppercase; margin-bottom:0.25rem;} .inp{width:100%; border-radius:0.5rem; border:1px solid #cbd5e1; font-size:0.875rem; padding:0.625rem;}</style>
    """
    return render_template_string(HTML_HEAD + content + HTML_FOOTER, reservas=reservas, session=session)

@app.route('/reservar', methods=['POST'])
def reservar():
    d = request.form
    nombre, registro, ci, celular, email = d['nombre'], d['registro'], d['ci'], d['celular'], d['email']
    resp = d.get('responsable_actividad') or nombre
    tipo, obj, fecha, ini, fin, part = d['tipo_actividad'], d['objetivo'], d['fecha'], d['inicio'], d['fin'], d['participantes']

    dias = (datetime.strptime(fecha, '%Y-%m-%d').date() - datetime.now().date()).days
    if dias < 3: return "<script>alert('Error: 72 hrs de anticipación requeridas.'); window.history.back();</script>"
    if ini >= fin: return "<script>alert('Error en horario.'); window.history.back();</script>"
    if hay_cruce_de_horario(fecha, ini, fin): return "<script>alert('Horario ocupado.'); window.history.back();</script>"

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''INSERT INTO reservas_laboratorio (nombre, registro, ci, celular, email, responsable_actividad, tipo_actividad, objetivo, fecha, hora_inicio, hora_fin, participantes) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''', 
                (nombre, registro, ci, celular, email, resp, tipo, obj, fecha, ini, fin, part))
    nid = cur.lastrowid
    conn.commit(); conn.close()
    
    msg = f"""
    <div class="min-h-[60vh] flex items-center justify-center p-4">
        <div class="bg-white rounded-2xl shadow-xl p-8 max-w-lg w-full text-center border border-emerald-100">
            <h2 class="text-2xl font-bold text-slate-900 mb-2">¡Solicitud Recibida!</h2>
            <p class="text-slate-600 mb-6">Descargue la carta y preséntela.</p>
            <a href="/descargar_carta/{nid}" class="block w-full py-3 bg-slate-900 text-white font-bold rounded-xl shadow-lg mb-3">📥 Descargar Carta (PDF)</a>
            <a href="/reservalab" class="block w-full py-3 border border-slate-300 text-slate-700 font-bold rounded-xl">Volver al Inicio</a>
        </div>
    </div>"""
    return render_template_string(HTML_HEAD + msg + HTML_FOOTER, session=session)

@app.route('/descargar_carta/<int:id_reserva>')
def descargar_carta(id_reserva):
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    cur.execute("SELECT * FROM reservas_laboratorio WHERE id = ?", (id_reserva,))
    res = cur.fetchone(); conn.close()
    if not res: return "No encontrado", 404
    datos = {'nombre': res[1], 'registro': res[2], 'ci': res[3], 'tipo_actividad': res[7], 'objetivo': res[8], 'fecha': res[9], 'hora_inicio': res[10], 'hora_fin': res[11], 'participantes': res[12]}
    
    response = make_response(crear_carta_pdf(datos))
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=Carta_{id_reserva}.pdf'
    return response

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if check_password_hash(PASSWORD_HASH, request.form['password']):
            session['admin_logueado'] = True
            return redirect('/admin')
        return "<script>alert('Error'); history.back();</script>"
    return render_template_string(HTML_HEAD + """<div class="flex justify-center pt-20"><div class="w-full max-w-sm bg-white p-8 rounded-xl shadow-lg"><h2 class="text-xl font-bold text-center mb-6">Acceso Director</h2><form method="POST" class="space-y-4"><input type="password" name="password" placeholder="Contraseña" class="w-full p-3 border rounded-lg"><button class="w-full py-3 bg-slate-900 text-white font-bold rounded-lg">Entrar</button></form></div></div>""" + HTML_FOOTER, session=session)

@app.route('/admin')
def admin_panel():
    if not session.get('admin_logueado'): return redirect('/login')
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    cur.execute("SELECT id, nombre, tipo_actividad, objetivo, fecha, hora_inicio, hora_fin, participantes FROM reservas_laboratorio WHERE estado='Pendiente'")
    pendientes = cur.fetchall(); conn.close()
    
    content = """<div class="max-w-4xl mx-auto pt-8 px-4"><div class="flex justify-between mb-6"><h2 class="text-2xl font-bold">Pendientes</h2><a href="/descargar_reporte" class="bg-emerald-600 text-white px-4 py-2 rounded-lg font-bold">Excel</a></div><div class="bg-white rounded-xl shadow overflow-hidden"><ul>{% for p in pendientes %}<li class="p-4 border-b hover:bg-slate-50 flex justify-between gap-4"><div><p class="font-bold">{{ p[1] }}</p><p class="text-sm text-slate-600">{{ p[2] }} ({{ p[4] }} {{ p[5] }}-{{ p[6] }})</p></div><form action="/procesar_reserva" method="POST" class="flex gap-2"><input type="hidden" name="id" value="{{ p[0] }}"><button name="accion" value="Aprobar" class="bg-emerald-100 text-emerald-700 px-3 py-1 rounded font-bold">✔</button><button name="accion" value="Rechazar" class="bg-rose-100 text-rose-700 px-3 py-1 rounded font-bold">✖</button></form></li>{% else %}<li class="p-8 text-center text-slate-400">Sin pendientes</li>{% endfor %}</ul></div></div>"""
    return render_template_string(HTML_HEAD + content + HTML_FOOTER, session=session)

@app.route('/procesar_reserva', methods=['POST'])
def procesar():
    if not session.get('admin_logueado'): return redirect('/login')
    estado = "Aprobada" if request.form['accion'] == "Aprobar" else "Rechazada"
    conn = sqlite3.connect(DB_PATH); conn.execute("UPDATE reservas_laboratorio SET estado = ? WHERE id = ?", (estado, request.form['id'])); conn.commit(); conn.close()
    return redirect('/admin')

@app.route('/descargar_reporte')
def descargar_reporte():
    if not session.get('admin_logueado'): return redirect('/login')
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor(); cur.execute("SELECT * FROM reservas_laboratorio"); data = cur.fetchall(); cols = [d[0] for d in cur.description]; conn.close()
    si = io.StringIO(); cw = csv.writer(si); cw.writerow(cols); cw.writerows(data)
    resp = make_response(si.getvalue()); resp.headers["Content-Disposition"] = "attachment; filename=reporte.csv"; resp.headers["Content-type"] = "text/csv"
    return resp

@app.route('/logout')
def logout(): session.pop('admin_logueado', None); return redirect('/reservalab')

if __name__ == '__main__':
    # Esta configuración es la necesaria para Render
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
