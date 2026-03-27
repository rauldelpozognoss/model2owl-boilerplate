import xml.etree.ElementTree as ET
import sys
import os # Añadido para extraer el nombre del archivo automáticamente

# --- CONFIGURACIÓN ---
NAMESPACE_XMI_OUTPUT = "http://www.omg.org/spec/XMI/20131001"

def map_datatype(href_string):
    if not href_string: return "xsd:string"
    href = href_string.lower()
    if "string" in href: return "xsd:string"
    if "edate" in href or "date" in href: return "xsd:date"
    if "integer" in href or "int" in href: return "xsd:integer"
    if "boolean" in href: return "xsd:boolean"
    return "xsd:string"

def get_multiplicity(element, ns):
    lower = element.find("./lowerValue", ns)
    upper = element.find("./upperValue", ns)
    l_val = lower.get("value", "0") if lower is not None else "1"
    u_val = upper.get("value", "1") if upper is not None else "1"
    if u_val == "-1": u_val = "*"
    return f"{l_val}..{u_val}"

def extraer_documentacion(elemento, ns):
    """Busca etiquetas <ownedComment> dentro de un elemento de Modelio y extrae su texto."""
    if elemento is None: return ""
    comentarios = elemento.findall("./ownedComment", ns)
    textos = []
    for com in comentarios:
        if "body" in com.attrib:
            textos.append(com.attrib["body"])
        else:
            body_node = com.find("./body", ns)
            if body_node is not None and body_node.text:
                textos.append(body_node.text)
    
    if textos:
        return " ".join(textos).replace("\r", " ").replace("\n", " ").strip()
    return ""

def adaptar_modelio_a_ea(input_file, output_file, prefijo_input):
    # Asegurarnos de que el prefijo termina siempre en ':'
    prefijo = prefijo_input if prefijo_input.endswith(':') else f"{prefijo_input}:"

    ET.register_namespace("xmi", NAMESPACE_XMI_OUTPUT)
    tree = ET.parse(input_file)
    root_modelio = tree.getroot()
    ns = {'xmi': 'http://schema.omg.org/spec/XMI/2.1', 'uml': 'http://www.eclipse.org/uml2/3.0.0/UML'}

    root_ea = ET.Element(f"{{{NAMESPACE_XMI_OUTPUT}}}XMI", {"xmi:version": "2.1"})
    extension = ET.SubElement(root_ea, f"{{{NAMESPACE_XMI_OUTPUT}}}Extension", {"extender": "Enterprise Architect"})
    elements = ET.SubElement(extension, "elements")
    connectors = ET.SubElement(extension, "connectors")

    catalog = {}
    for el in root_modelio.findall(".//packagedElement", ns):
        eid = el.get(f"{{{ns['xmi']}}}id")
        etype = el.get(f"{{{ns['xmi']}}}type")
        ename = el.get('name', 'Unnamed')
        
        if etype in ['uml:Class', 'uml:Enumeration', 'uml:PrimitiveType']:
            has_parent = el.find("./generalization", ns) is not None
            catalog[eid] = {
                'name': ename, 
                'type': etype.replace('uml:', '') if etype else 'Class',
                'has_parent': has_parent
            }

    root_class_id = "ID_AUTO_GENERATED_THING_ROOT"
    ea_root = ET.SubElement(elements, "element", {
        f"{{{NAMESPACE_XMI_OUTPUT}}}type": "uml:Class",
        f"{{{NAMESPACE_XMI_OUTPUT}}}idref": root_class_id,
        "name": f"{prefijo}Thing"
    })
    ET.SubElement(ea_root, "properties", {"documentation": "Clase raíz del metamodelo. Todas las clases diseñadas cuelgan de aquí."})

    for eid, info in catalog.items():
        if info['name'] == "Thing": continue

        m2o_type = 'uml:Class'
        if info['type'] == 'Enumeration': m2o_type = 'uml:Enumeration'
        if info['type'] == 'PrimitiveType': m2o_type = 'uml:DataType'

        ea_element = ET.SubElement(elements, "element", {
            f"{{{NAMESPACE_XMI_OUTPUT}}}type": m2o_type,
            f"{{{NAMESPACE_XMI_OUTPUT}}}idref": eid,
            "name": f"{prefijo}{info['name']}"
        })
        
        original_el = root_modelio.find(f".//*[@xmi:id='{eid}']", ns)
        
        doc_text = extraer_documentacion(original_el, ns)
        props = ET.SubElement(ea_element, "properties")
        if doc_text: 
            props.set("documentation", doc_text)
        if original_el.get("isAbstract") == "true": 
            props.set("stereotype", "Abstract")

        attr_container = ET.SubElement(ea_element, "attributes")
        for attr in original_el.findall("./ownedAttribute", ns):
            if attr.get("association"): continue
            aid = attr.get(f"{{{ns['xmi']}}}id")
            aname = attr.get("name")
            
            final_attr_name = f"{prefijo}has{aname[:1].upper() + aname[1:]}" if info['type'] == 'Class' else f"{prefijo}{aname}"
            
            ea_attr = ET.SubElement(attr_container, "attribute", {
                f"{{{NAMESPACE_XMI_OUTPUT}}}idref": aid,
                "name": final_attr_name
            })
            
            attr_doc = extraer_documentacion(attr, ns)
            if attr_doc:
                ET.SubElement(ea_attr, "documentation", {"value": attr_doc})
            
            t_node = attr.find("./type", ns)
            t_xsd = map_datatype(t_node.get("href")) if t_node is not None else "xsd:string"
            ET.SubElement(ea_attr, "properties", {"type": t_xsd})
            
            lower_node = attr.find("./lowerValue", ns)
            upper_node = attr.find("./upperValue", ns)
            
            l_val = lower_node.get("value", "0") if lower_node is not None else "1"
            u_val = upper_node.get("value", "1") if upper_node is not None else "1"
            if u_val == "-1": 
                u_val = "*"
                
            ET.SubElement(ea_attr, "bounds", {"lower": str(l_val), "upper": str(u_val)})

        if not info['has_parent'] and info['type'] in ['Class', 'Enumeration']:
            gen_id = f"auto_gen_thing_{eid}"
            ea_gen = ET.SubElement(connectors, "connector", {f"{{{NAMESPACE_XMI_OUTPUT}}}idref": gen_id})
            ET.SubElement(ea_gen, "properties", {"ea_type": "Generalization", "direction": "Source -> Destination"})
            
            src = ET.SubElement(ea_gen, "source", {f"{{{NAMESPACE_XMI_OUTPUT}}}idref": eid})
            ET.SubElement(src, "model", {"name": f"{prefijo}{info['name']}", "type": "Class"})
            
            tgt = ET.SubElement(ea_gen, "target", {f"{{{NAMESPACE_XMI_OUTPUT}}}idref": root_class_id})
            ET.SubElement(tgt, "model", {"name": f"{prefijo}Thing", "type": "Class"})

    for eid, info in catalog.items():
        if info['type'] != 'Class': continue
        original_el = root_modelio.find(f".//*[@xmi:id='{eid}']", ns)
        for attr in original_el.findall("./ownedAttribute[@association]", ns):
            tid = attr.get("type")
            if tid in catalog:
                aid = attr.get("association")
                ea_conn = ET.SubElement(connectors, "connector", {f"{{{NAMESPACE_XMI_OUTPUT}}}idref": aid})
                ET.SubElement(ea_conn, "properties", {"ea_type": "Association", "direction": "Source -> Destination"})
                
                conn_doc = extraer_documentacion(attr, ns)
                if conn_doc:
                    ET.SubElement(ea_conn, "documentation", {"value": conn_doc})
                
                ET.SubElement(ET.SubElement(ea_conn, "source", {f"{{{NAMESPACE_XMI_OUTPUT}}}idref": eid}), "model", {"name": f"{prefijo}{info['name']}", "type": "Class"})
                
                target = ET.SubElement(ea_conn, "target", {f"{{{NAMESPACE_XMI_OUTPUT}}}idref": tid})
                ET.SubElement(target, "model", {"name": f"{prefijo}{catalog[tid]['name']}", "type": catalog[tid]['type']})
                ET.SubElement(target, "type", {"multiplicity": get_multiplicity(attr, ns)})
                ET.SubElement(target, "role", {"name": f"{prefijo}has{attr.get('name')[:1].upper() + attr.get('name')[1:]}", "visibility": "Public"})

    for gen in root_modelio.findall(".//generalization", ns):
        rid = gen.get(f"{{{ns['xmi']}}}id")
        tid = gen.get("general")
        child_el = root_modelio.find(f".//*[@xmi:id='{rid}']/..", ns)
        sid = child_el.get(f"{{{ns['xmi']}}}id")
        
        if sid in catalog and tid in catalog:
            ea_gen = ET.SubElement(connectors, "connector", {f"{{{NAMESPACE_XMI_OUTPUT}}}idref": rid})
            ET.SubElement(ea_gen, "properties", {"ea_type": "Generalization", "direction": "Source -> Destination"})
            ET.SubElement(ET.SubElement(ea_gen, "source", {f"{{{NAMESPACE_XMI_OUTPUT}}}idref": sid}), "model", {"name": f"{prefijo}{catalog[sid]['name']}", "type": "Class"})
            ET.SubElement(ET.SubElement(ea_gen, "target", {f"{{{NAMESPACE_XMI_OUTPUT}}}idref": tid}), "model", {"name": f"{prefijo}{catalog[tid]['name']}", "type": "Class"})

    for rel_type, ea_label in [("Dependency", "Dependency"), ("Realization", "Realization")]:
        for rel in root_modelio.findall(f".//packagedElement[@xmi:type='uml:{rel_type}']", ns):
            sid = rel.get("client"); tid = rel.get("supplier"); rid = rel.get(f"{{{ns['xmi']}}}id")
            
            rel_name = rel.get("name", "")
            stereotype = ""
            if "disjoint" in rel_name.lower(): stereotype = "Disjoint"
            if "equivalent" in rel_name.lower(): stereotype = "Equivalent"

            if sid in catalog and tid in catalog:
                ea_conn = ET.SubElement(connectors, "connector", {f"{{{NAMESPACE_XMI_OUTPUT}}}idref": rid})
                
                props = {"ea_type": ea_label, "direction": "Source -> Destination"}
                if stereotype: props["stereotype"] = stereotype
                ET.SubElement(ea_conn, "properties", props)
                
                rel_doc = extraer_documentacion(rel, ns)
                if rel_doc: ET.SubElement(ea_conn, "documentation", {"value": rel_doc})

                ET.SubElement(ET.SubElement(ea_conn, "source", {f"{{{NAMESPACE_XMI_OUTPUT}}}idref": sid}), "model", {"name": f"{prefijo}{catalog[sid]['name']}", "type": catalog[sid]['type']})
                tgt = ET.SubElement(ea_conn, "target", {f"{{{NAMESPACE_XMI_OUTPUT}}}idref": tid})
                ET.SubElement(tgt, "model", {"name": f"{prefijo}{catalog[tid]['name']}", "type": catalog[tid]['type']})
                ET.SubElement(tgt, "role", {"name": f"{prefijo}has{catalog[tid]['name']}", "visibility": "Public"})
                
    tree_ea = ET.ElementTree(root_ea)
    tree_ea.write(output_file, encoding="UTF-8", xml_declaration=True)
    print(f"¡Éxito! XML generado con prefijo automático '{prefijo}', cardinalidad dinámica y compatibilidad total con EA.")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python modelio_to_ea.py <entrada.xmi> <salida.xml>")
        print("Ejemplo: python modelio_to_ea.py prueba.xmi prueba_ea.xml")
    else:
        input_file = sys.argv[1]
        output_file = sys.argv[2]
        
        # --- EXTRACCIÓN AUTOMÁTICA DEL PREFIJO ---
        # 1. Cogemos solo el nombre del archivo (ej: C:/mis_modelos/prueba.xmi -> prueba.xmi)
        base_name = os.path.basename(input_file)
        
        # 2. Le quitamos la extensión (ej: prueba.xmi -> prueba)
        prefijo_detectado, _ = os.path.splitext(base_name)
        
        # 3. Llamamos a la función con el prefijo extraído automáticamente
        adaptar_modelio_a_ea(input_file, output_file, prefijo_detectado)