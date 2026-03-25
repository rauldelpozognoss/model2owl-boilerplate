import xml.etree.ElementTree as ET
import sys

# Configuración del proyecto
PREFIJO = "prueba:"
NAMESPACE_XMI_OUTPUT = "http://www.omg.org/spec/XMI/20131001"

def map_datatype(href_string):
    """Mapea los tipos de datos de Modelio a XSD estándar"""
    if not href_string: return "xsd:string"
    href = href_string.lower()
    if "string" in href: return "xsd:string"
    if "edate" in href or "date" in href: return "xsd:date"
    if "integer" in href or "int" in href: return "xsd:integer"
    if "boolean" in href: return "xsd:boolean"
    if "double" in href or "real" in href: return "xsd:double"
    return "xsd:string"

def get_multiplicity(element, ns):
    """Extrae la cadena de multiplicidad (ej: 0..*)"""
    lower = element.find("./lowerValue", ns)
    upper = element.find("./upperValue", ns)
    l_val = lower.get("value", "0") if lower is not None else "1"
    u_val = upper.get("value", "1") if upper is not None else "1"
    if u_val == "-1": u_val = "*" # Unlimited en UML es -1
    return f"{l_val}..{u_val}"

def adaptar_modelio_a_ea(input_file, output_file):
    ET.register_namespace("xmi", NAMESPACE_XMI_OUTPUT)
    tree = ET.parse(input_file)
    root_modelio = tree.getroot()

    ns = {'xmi': 'http://schema.omg.org/spec/XMI/2.1', 'uml': 'http://www.eclipse.org/uml2/3.0.0/UML'}

    root_ea = ET.Element(f"{{{NAMESPACE_XMI_OUTPUT}}}XMI", {"xmi:version": "2.1"})
    extension = ET.SubElement(root_ea, f"{{{NAMESPACE_XMI_OUTPUT}}}Extension", {"extender": "Enterprise Architect"})
    elements = ET.SubElement(extension, "elements")
    connectors = ET.SubElement(extension, "connectors")

    # 1. MAPEADO DE IDs PARA RESOLUCIÓN DE NOMBRES
    catalog = {}
    for el in root_modelio.findall(".//packagedElement", ns):
        eid = el.get(f"{{{ns['xmi']}}}id")
        etype = el.get(f"{{{ns['xmi']}}}type")
        catalog[eid] = {
            'name': el.get('name', 'Unnamed'),
            'type': etype.replace('uml:', '') if etype else 'Class'
        }

    # 2. PROCESAR ELEMENTOS (Classes, Enumerations, PrimitiveTypes)
    for el in root_modelio.findall(".//packagedElement", ns):
        etype = el.get(f"{{{ns['xmi']}}}type")
        if etype not in ['uml:Class', 'uml:Enumeration', 'uml:PrimitiveType']: continue
        
        eid = el.get(f"{{{ns['xmi']}}}id")
        ename = el.get("name")
        is_abstract = el.get("isAbstract") == "true"
        
        # Mapeo de tipo de elemento para model2owl
        m2o_type = etype
        if etype == 'uml:PrimitiveType': m2o_type = 'uml:DataType'

        ea_element = ET.SubElement(elements, "element", {
            f"{{{NAMESPACE_XMI_OUTPUT}}}type": m2o_type,
            f"{{{NAMESPACE_XMI_OUTPUT}}}idref": eid,
            "name": f"{PREFIJO}{ename}"
        })
        
        # Propiedades EA (Abstract)
        props = ET.SubElement(ea_element, "properties", {"documentation": "Importado de Modelio"})
        if is_abstract: props.set("stereotype", "Abstract")

        # ATRIBUTOS
        attr_container = ET.SubElement(ea_element, "attributes")
        for attr in el.findall("./ownedAttribute", ns):
            if attr.get("association"): continue # Es una relación, no un atributo literal
            
            aid = attr.get(f"{{{ns['xmi']}}}id")
            aname = attr.get("name")
            
            # Convención de nombres (hasNombre para Clases, nombre simple para Enums)
            final_name = f"{PREFIJO}has{aname[:1].upper() + aname[1:]}" if etype == 'uml:Class' else f"{PREFIJO}{aname}"
            
            ea_attr = ET.SubElement(attr_container, "attribute", {
                f"{{{NAMESPACE_XMI_OUTPUT}}}idref": aid,
                "name": final_name
            })
            
            # Tipo de dato
            t_node = attr.find("./type", ns)
            t_xsd = "xsd:string"
            if t_node is not None:
                t_id = t_node.get("type")
                if t_id and t_id in catalog: t_xsd = f"{PREFIJO}{catalog[t_id]['name']}" # Tipo personalizado
                else: t_xsd = map_datatype(t_node.get("href")) # Tipo primitivo
            
            ET.SubElement(ea_attr, "properties", {"type": t_xsd})
            
            # Multiplicidad
            lower = attr.find("./lowerValue", ns); upper = attr.find("./upperValue", ns)
            ET.SubElement(ea_attr, "bounds", {
                "lower": lower.get("value", "0") if lower is not None else "1",
                "upper": upper.get("value", "1") if upper is not None else "1"
            })

    # 3. PROCESAR CONECTORES (Associations, Dependencies, Realizations, Generalizations)
    
    # 3.1 Asociaciones (basadas en ownedAttribute con association)
    for el in root_modelio.findall(".//packagedElement[@xmi:type='uml:Class']", ns):
        sid = el.get(f"{{{ns['xmi']}}}id")
        for attr in el.findall("./ownedAttribute[@association]", ns):
            tid = attr.get("type")
            if tid not in catalog: continue
            
            ea_conn = ET.SubElement(connectors, "connector", {f"{{{NAMESPACE_XMI_OUTPUT}}}idref": attr.get("association")})
            ET.SubElement(ea_conn, "properties", {"ea_type": "Association", "direction": "Source -> Destination"})
            
            src = ET.SubElement(ea_conn, "source", {f"{{{NAMESPACE_XMI_OUTPUT}}}idref": sid})
            ET.SubElement(src, "model", {"name": f"{PREFIJO}{catalog[sid]['name']}", "type": "Class"})
            ET.SubElement(src, "role", {"visibility": "Public"})
            
            tgt = ET.SubElement(ea_conn, "target", {f"{{{NAMESPACE_XMI_OUTPUT}}}idref": tid})
            ET.SubElement(tgt, "model", {"name": f"{PREFIJO}{catalog[tid]['name']}", "type": catalog[tid]['type']})
            ET.SubElement(tgt, "type", {"multiplicity": get_multiplicity(attr, ns)})
            ET.SubElement(tgt, "role", {"name": f"{PREFIJO}has{attr.get('name')[:1].upper() + attr.get('name')[1:]}", "visibility": "Public"})

    # 3.2 Generalizaciones, Dependencias y Realizaciones
    for rel_type, ea_label in [("generalization", "Generalization"), ("Dependency", "Dependency"), ("Realization", "Realization")]:
        path = f".//packagedElement[@xmi:type='uml:{rel_type}']" if rel_type != "generalization" else ".//generalization"
        for rel in root_modelio.findall(path, ns):
            rid = rel.get(f"{{{ns['xmi']}}}id")
            
            if rel_type == "generalization":
                sid = rel.getparent().get(f"{{{ns['xmi']}}}id") if hasattr(rel, 'getparent') else root_modelio.find(f".//*[@xmi:id='{rid}']/..", ns).get(f"{{{ns['xmi']}}}id")
                # Si getparent falla (xml estándar), buscamos el dueño de la etiqueta
                tid = rel.get("general")
            else:
                sid = rel.get("client")
                tid = rel.get("supplier")
            
            if sid not in catalog or tid not in catalog: continue

            ea_conn = ET.SubElement(connectors, "connector", {f"{{{NAMESPACE_XMI_OUTPUT}}}idref": rid})
            ET.SubElement(ea_conn, "properties", {"ea_type": ea_label, "direction": "Source -> Destination"})
            ET.SubElement(ET.SubElement(ea_conn, "source", {f"{{{NAMESPACE_XMI_OUTPUT}}}idref": sid}), "model", {"name": f"{PREFIJO}{catalog[sid]['name']}", "type": catalog[sid]['type']})
            ET.SubElement(ET.SubElement(ea_conn, "target", {f"{{{NAMESPACE_XMI_OUTPUT}}}idref": tid}), "model", {"name": f"{PREFIJO}{catalog[tid]['name']}", "type": catalog[tid]['type']})

    tree_ea = ET.ElementTree(root_ea)
    tree_ea.write(output_file, encoding="UTF-8", xml_declaration=True)
    print(f"¡Éxito! Modelo Frankenstein procesado en: {output_file}")

if __name__ == "__main__":
    adaptar_modelio_a_ea(sys.argv[1], sys.argv[2])