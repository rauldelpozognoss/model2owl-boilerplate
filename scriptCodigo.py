import os
from pathlib import Path

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================

# 1. Ruta de la carpeta de tu proyecto (El punto significa la carpeta actual)
directorio_proyecto = "."

# 2. Ruta y nombre del archivo de texto donde se guardará todo
archivo_salida = "salida_codigo.txt" 

# 3. Extensiones que quieres incluir (Añade o quita según necesites)
extensiones = {".py", ".xml"}

# ==============================================================================
# EJECUCIÓN DEL SCRIPT
# ==============================================================================

# Códigos para colorear la salida en la consola
CYAN = '\033[96m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
RESET = '\033[0m'

print(f"{CYAN}Iniciando la recopilación de archivos...{RESET}")

# Eliminar el archivo de salida si ya existe para no duplicar contenido
if os.path.exists(archivo_salida):
    os.remove(archivo_salida)

contador = 0
ruta_base = Path(directorio_proyecto)

# Abrimos el archivo de salida en modo "append" (añadir) con codificación UTF-8
with open(archivo_salida, "a", encoding="utf-8") as f_salida:
    
    # Buscar todos los archivos de forma recursiva (incluyendo subcarpetas)
    for archivo in ruta_base.rglob("*"):
        
        # Comprobar si es un archivo y si su extensión está en nuestra lista (en minúsculas)
        if archivo.is_file() and archivo.suffix.lower() in extensiones:
            
            # Crear un encabezado visible para separar los archivos en el txt
            separador = "\n======================================================================\n"
            cabecera = f"ARCHIVO: {archivo.resolve()}\n"
            separador_final = "======================================================================\n"
            
            # Escribir el encabezado
            f_salida.write(separador + cabecera + separador_final)
            
            try:
                # Intentar leer el contenido del archivo original
                with open(archivo, "r", encoding="utf-8") as f_entrada:
                    contenido = f_entrada.read()
                    
                    if contenido.strip():
                        f_salida.write(contenido + "\n")
                    else:
                        f_salida.write("[El archivo está vacío]\n")
            
            except UnicodeDecodeError:
                f_salida.write("[Error: El archivo no es texto válido o tiene otra codificación]\n")
            except Exception as e:
                f_salida.write(f"[No se pudo leer el archivo: {e}]\n")
            
            contador += 1

print(f"{GREEN}Proceso completado exitosamente.{RESET}")
print(f"{YELLOW}Se han procesado {contador} archivos.{RESET}")
print(f"{YELLOW}Puedes revisar el resultado en: {Path(archivo_salida).resolve()}{RESET}")