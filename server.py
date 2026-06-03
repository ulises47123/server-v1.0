#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import socket
import json
import subprocess
from http.server import HTTPServer, SimpleHTTPRequestHandler
import urllib.parse

ARCHIVO_CONFIG = "server_config.json"
ARCHIVO_METADATOS = "metadatos.json"

def capitalizar_palabras(texto):
    if not texto:
        return texto
    return ' '.join(p.capitalize() for p in texto.split())

def obtener_ip_local():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def cargar_config(ruta_www):
    archivo = os.path.join(ruta_www, ARCHIVO_CONFIG)
    if os.path.exists(archivo):
        try:
            with open(archivo, 'r') as f:
                return json.load(f)
        except:
            return {"nombre_personalizado": None}
    return {"nombre_personalizado": None}

def guardar_config(ruta_www, config):
    archivo = os.path.join(ruta_www, ARCHIVO_CONFIG)
    with open(archivo, 'w') as f:
        json.dump(config, f)

def buscar_carpeta_www():
    actual = os.getcwd()
    ruta_www = os.path.join(actual, "www")
    if os.path.isdir(ruta_www):
        return ruta_www
    print(f"No se encontró la carpeta 'www' en {actual}")
    respuesta = input("Ruta completa de la carpeta 'www': ").strip()
    if os.path.isdir(respuesta):
        return os.path.abspath(respuesta)
    print("Directorio inválido.")
    sys.exit(1)

def verificar_index_html(directorio):
    indice = os.path.join(directorio, "index.html")
    if os.path.isfile(indice):
        return True
    print("Advertencia: no se encontró index.html")
    if input("Continuar de todos modos? (s/n): ").strip().lower() != 's':
        sys.exit(0)
    return False

def verificar_zeroconf():
    try:
        from zeroconf import Zeroconf, ServiceInfo
        return True
    except ImportError:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "zeroconf"],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            from zeroconf import Zeroconf, ServiceInfo
            return True
        except:
            return False

def registrar_mdns(nombre, puerto, ip):
    from zeroconf import Zeroconf, ServiceInfo
    if not nombre.endswith('.local'):
        nombre = nombre + '.local'
    direccion_bytes = socket.inet_aton(ip)
    info = ServiceInfo(
        "_http._tcp.local.",
        f"{nombre}._http._tcp.local.",
        addresses=[direccion_bytes],
        port=puerto,
        properties={"path": "/"},
        server=nombre,
    )
    zc = Zeroconf()
    zc.register_service(info)
    return zc

def cargar_metadatos(ruta_www):
    archivo = os.path.join(ruta_www, ARCHIVO_METADATOS)
    if not os.path.exists(archivo):
        return {}
    try:
        with open(archivo, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}

def guardar_metadatos(ruta_www, metadatos):
    archivo = os.path.join(ruta_www, ARCHIVO_METADATOS)
    with open(archivo, 'w', encoding='utf-8') as f:
        json.dump(metadatos, f, indent=2, ensure_ascii=False)

def listar_archivos_con_metadatos(ruta_www):
    carpeta_archivos = os.path.join(ruta_www, "archivos")
    if not os.path.isdir(carpeta_archivos):
        return []
    metadatos = cargar_metadatos(ruta_www)
    archivos = []
    metadatos_actualizados = {}
    for nombre, meta in metadatos.items():
        if os.path.isfile(os.path.join(carpeta_archivos, nombre)):
            metadatos_actualizados[nombre] = meta
    if len(metadatos_actualizados) != len(metadatos):
        guardar_metadatos(ruta_www, metadatos_actualizados)
        metadatos = metadatos_actualizados
    for nombre in os.listdir(carpeta_archivos):
        ruta_completa = os.path.join(carpeta_archivos, nombre)
        if os.path.isfile(ruta_completa):
            meta = metadatos.get(nombre, {})
            categoria = meta.get("categoria", "Sin Categoría")
            descripcion = meta.get("descripcion", "")
            archivos.append({
                "nombre": nombre,
                "descripcion": descripcion,
                "categoria": categoria,
                "url": f"archivos/{urllib.parse.quote(nombre)}"
            })
    return archivos

def obtener_nuevos_archivos(ruta_www):
    carpeta_archivos = os.path.join(ruta_www, "archivos")
    if not os.path.isdir(carpeta_archivos):
        return []
    metadatos = cargar_metadatos(ruta_www)
    nuevos = []
    for nombre in os.listdir(carpeta_archivos):
        if os.path.isfile(os.path.join(carpeta_archivos, nombre)) and nombre not in metadatos:
            nuevos.append(nombre)
    return nuevos

def clasificar_archivo(ruta_www, nombre, categoria, descripcion):
    carpeta_archivos = os.path.join(ruta_www, "archivos")
    if not os.path.isfile(os.path.join(carpeta_archivos, nombre)):
        return False
    metadatos = cargar_metadatos(ruta_www)
    metadatos[nombre] = {
        "categoria": capitalizar_palabras(categoria),
        "descripcion": descripcion  # No capitalizamos descripción completa, solo primera letra? Opcional.
    }
    guardar_metadatos(ruta_www, metadatos)
    return True

def editar_metadato(ruta_www, nombre, categoria, descripcion):
    carpeta_archivos = os.path.join(ruta_www, "archivos")
    if not os.path.isfile(os.path.join(carpeta_archivos, nombre)):
        return False
    metadatos = cargar_metadatos(ruta_www)
    if nombre not in metadatos:
        return False
    metadatos[nombre] = {
        "categoria": capitalizar_palabras(categoria),
        "descripcion": descripcion
    }
    guardar_metadatos(ruta_www, metadatos)
    return True

def renombrar_categoria(ruta_www, vieja, nueva):
    metadatos = cargar_metadatos(ruta_www)
    cambiado = False
    for nombre, meta in metadatos.items():
        if meta.get('categoria') == vieja:
            meta['categoria'] = capitalizar_palabras(nueva)
            cambiado = True
    if cambiado:
        guardar_metadatos(ruta_www, metadatos)
        return True
    return False

class ServidorPersonalizado(HTTPServer):
    def __init__(self, server_address, RequestHandlerClass, www_dir):
        super().__init__(server_address, RequestHandlerClass)
        self.www_dir = www_dir

class ManejadorAPI(SimpleHTTPRequestHandler):
    def do_GET(self):
        try:
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == '/api/archivos':
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                archivos = listar_archivos_con_metadatos(self.server.www_dir)
                self.wfile.write(json.dumps(archivos, ensure_ascii=False).encode('utf-8'))
                return
            elif parsed.path == '/api/nuevos':
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                nuevos = obtener_nuevos_archivos(self.server.www_dir)
                self.wfile.write(json.dumps(nuevos, ensure_ascii=False).encode('utf-8'))
                return
            elif parsed.path == '/api/categorias':
                archivos = listar_archivos_con_metadatos(self.server.www_dir)
                categorias = sorted(set(a['categoria'] for a in archivos))
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(categorias, ensure_ascii=False).encode('utf-8'))
                return
            else:
                return SimpleHTTPRequestHandler.do_GET(self)
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        try:
            data = json.loads(body)
        except:
            self.send_error(400, "JSON inválido")
            return
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/api/clasificar':
            nombre = data.get('nombre')
            categoria = data.get('categoria')
            descripcion = data.get('descripcion', '')
            if not nombre or not categoria:
                self.send_error(400, "Faltan campos")
                return
            ok = clasificar_archivo(self.server.www_dir, nombre, categoria, descripcion)
            if ok:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok"}).encode())
            else:
                self.send_error(404, "Archivo no encontrado")
            return
        elif parsed.path == '/api/editar':
            nombre = data.get('nombre')
            categoria = data.get('categoria')
            descripcion = data.get('descripcion', '')
            if not nombre or not categoria:
                self.send_error(400, "Faltan campos")
                return
            ok = editar_metadato(self.server.www_dir, nombre, categoria, descripcion)
            if ok:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok"}).encode())
            else:
                self.send_error(404, "Archivo no encontrado o sin metadato")
            return
        elif parsed.path == '/api/renombrar_categoria':
            vieja = data.get('vieja')
            nueva = data.get('nueva')
            if not vieja or not nueva:
                self.send_error(400, "Faltan campos")
                return
            ok = renombrar_categoria(self.server.www_dir, vieja, nueva)
            if ok:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok"}).encode())
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Categoría no encontrada"}).encode())
            return
        else:
            self.send_error(404, "Endpoint no encontrado")

    def log_message(self, formato, *args):
        pass

def main():
    puerto = 8080
    directorio_www = buscar_carpeta_www()
    verificar_index_html(directorio_www)
    os.chdir(directorio_www)

    if not os.path.exists(ARCHIVO_METADATOS):
        guardar_metadatos(directorio_www, {})

    mdns_disponible = verificar_zeroconf()
    config = cargar_config(directorio_www)
    nombre_personal = None

    if mdns_disponible:
        nombre_guardado = config.get("nombre_personalizado")
        print("\nConfiguración del nombre personalizado (mDNS)")
        if nombre_guardado:
            print(f"Nombre actual: {nombre_guardado}")
            cambiar = input("¿Deseas cambiarlo? (s/n): ").strip().lower()
            if cambiar == 's':
                nombre_personal = input("Nuevo nombre (ej. anto o julian.local): ").strip()
                config["nombre_personalizado"] = nombre_personal
                guardar_config(directorio_www, config)
            else:
                nombre_personal = nombre_guardado
        else:
            nombre_personal = input("Nombre personalizado (vacío para omitir): ").strip()
            if nombre_personal:
                config["nombre_personalizado"] = nombre_personal
                guardar_config(directorio_www, config)
    else:
        print("\n[INFO] mDNS no disponible (zeroconf no instalable). Solo se usará IP.")

    ip_local = obtener_ip_local()
    print("\n" + "="*50)
    print(f"Servidor HTTP activo")
    print(f"  IP: http://{ip_local}:{puerto}")

    zc = None
    if mdns_disponible and nombre_personal:
        try:
            zc = registrar_mdns(nombre_personal, puerto, ip_local)
            nombre_mostrar = nombre_personal if nombre_personal.endswith('.local') else nombre_personal + '.local'
            print(f"  mDNS: http://{nombre_mostrar}:{puerto}")
        except Exception as e:
            print(f"  Error al registrar mDNS: {e}")
            print("  Usa la IP directamente.")
    elif not mdns_disponible:
        print("  (mDNS desactivado)")
    else:
        print("  Sin nombre personalizado, solo IP.")

    print(f"SIRVIENDO: {directorio_www}")
    print("Presiona Ctrl+C para detener")
    print("="*50)

    servidor = ServidorPersonalizado(('0.0.0.0', puerto), ManejadorAPI, directorio_www)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nDeteniendo servidor...")
        if zc:
            zc.close()
        sys.exit(0)

if __name__ == "__main__":
    main()
