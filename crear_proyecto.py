import os
import sys
import shutil
import json

def crear_nuevo_proyecto(nombre_proyecto, prefijo, base_uri, idioma="es"):
    # 1. Definir rutas
    plantilla_dir = os.path.join("implementation", "prueba")
    nuevo_dir = os.path.join("implementation", nombre_proyecto)
    
    if not os.path.exists(plantilla_dir):
        print("❌ Error: No se encuentra la carpeta de plantilla 'implementation/prueba'.")
        sys.exit(1)
        
    if os.path.exists(nuevo_dir):
        print(f"❌ Error: El proyecto '{nombre_proyecto}' ya existe.")
        sys.exit(1)

    print(f"🚀 Creando nuevo proyecto: {nombre_proyecto} (Prefijo: {prefijo})")

    # 2. Crear estructura de carpetas
    os.makedirs(nuevo_dir)
    os.makedirs(os.path.join(nuevo_dir, "xmi_conceptual_model"))
    config_dir_nuevo = os.path.join(nuevo_dir, "model2owl-config")
    os.makedirs(config_dir_nuevo)
    
    # Copiar respec_resources si existe en la plantilla
    respec_src = os.path.join(plantilla_dir, "respec_resources")
    if os.path.exists(respec_src):
        shutil.copytree(respec_src, os.path.join(nuevo_dir, "respec_resources"))
        print("✅ Carpeta respec_resources copiada.")

    # 3. Procesar archivos de configuración
    config_dir_plantilla = os.path.join(plantilla_dir, "model2owl-config")
    
    for filename in os.listdir(config_dir_plantilla):
        src_file = os.path.join(config_dir_plantilla, filename)
        dest_file = os.path.join(config_dir_nuevo, filename)
        
        # Ignorar directorios si los hubiera
        if not os.path.isfile(src_file): continue

        with open(src_file, 'r', encoding='utf-8') as f:
            contenido = f.read()

        # A) MODIFICAR namespaces.xml
        if filename == "namespaces.xml":
            # Cambiar el prefijo 'prueba' por el nuevo
            contenido = contenido.replace('name="prueba"', f'name="{prefijo}"')
            # Cambiar la URI de tu dominio
            contenido = contenido.replace('http://tu-dominio.com/ontologia/prueba', base_uri)
            
            with open(dest_file, 'w', encoding='utf-8') as f:
                f.write(contenido)
            print(f"✅ {filename} configurado.")

        # B) MODIFICAR config-parameters.xsl
        elif filename == "config-parameters.xsl":
            # Cambiar la URI base
            contenido = contenido.replace('http://tu-dominio.com/ontologia/prueba', base_uri)
            # Cambiar la lista de prefijos incluidos
            contenido = contenido.replace("select=\"('prueba')\"", f"select=\"('{prefijo}')\"")
            
            with open(dest_file, 'w', encoding='utf-8') as f:
                f.write(contenido)
            print(f"✅ {filename} configurado.")

        # C) MODIFICAR metadata.json
        elif filename == "metadata.json":
            data = json.loads(contenido)
            
            # Actualizar metadatos básicos
            data["metadata"]["conventionReportUMLModelName"] = nombre_proyecto.capitalize()
            data["metadata"]["ontologyTitleCore"] = f"Ontología {nombre_proyecto.capitalize()} Core"
            data["metadata"]["ontologyTitleRestrictions"] = f"Ontología {nombre_proyecto.capitalize()} Restricciones"
            data["metadata"]["ontologyTitleShapes"] = f"Ontología {nombre_proyecto.capitalize()} Shapes"
            data["metadata"]["title"] = f"Ontología {nombre_proyecto.capitalize()} Core"
            
            data["metadata"]["preferredNamespacePrefix"] = prefijo
            data["metadata"]["preferredNamespaceUri"] = f"{base_uri}#"
            
            # Actualizar rutas de archivos (cambiar 'prueba' por el nombre del nuevo proyecto)
            if "projectLocalResources" in data["metadata"]:
                for recurso in data["metadata"]["projectLocalResources"]:
                    # Reemplazamos 'prueba' por el nombre del módulo actual
                    recurso["path"] = recurso["path"].replace("prueba", nombre_proyecto)
            
            with open(dest_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            print(f"✅ {filename} configurado.")

        # D) COPIAR EL RESTO DE ARCHIVOS (imports.xml, umlToXsdDataTypes.xml, etc.)
        else:
            shutil.copy2(src_file, dest_file)
            # print(f"  - {filename} copiado tal cual.")

    print("\n🎉 ¡Proyecto creado con éxito!")
    print(f"👉 Siguiente paso: Guarda tu archivo de Modelio como 'implementation/{nombre_proyecto}/xmi_conceptual_model/{nombre_proyecto}.xml'")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Uso: python crear_proyecto.py <nombre_carpeta> <prefijo> <base_uri> [idioma]")
        print("Ejemplo: python crear_proyecto.py sosa sosa http://www.w3.org/ns/sosa es")
    else:
        nombre = sys.argv[1]
        pref = sys.argv[2]
        uri = sys.argv[3]
        idioma = sys.argv[4] if len(sys.argv) > 4 else "es"
        
        crear_nuevo_proyecto(nombre, pref, uri, idioma)