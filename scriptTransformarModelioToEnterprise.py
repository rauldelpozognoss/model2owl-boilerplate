import xml.etree.ElementTree as ET
import sys

# Configuración
PREFIJO = "prueba:"
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

def adaptar_modelio_a_ea(input_file, output_file):
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
        catalog[eid] = {
            'name': el.get('name', 'Unnamed'), 
            'type': etype.replace('uml:', '') if etype else 'Class',
            'has_parent': el.find("./generalization", ns) is not None
        }

    # --- INYECCIÓN DE RAÍZ PRUEBA:THING ---
    root_class_id = "ID_PRUEBA_THING_ROOT"
    ea_root = ET.SubElement(elements, "element", {
        f"{{{NAMESPACE_XMI_OUTPUT}}}type": "uml:Class",
        f"{{{NAMESPACE_XMI_OUTPUT}}}idref": root_class_id,
        "name": f"{PREFIJO}Thing"
    })
    ET.SubElement(ea_root, "properties", {"documentation": "Clase raíz para colapsar el metamodelo de prueba."})

    # 1. ELEMENTOS (CLASES, ENUMS, DATATYPES)
    for el in root_modelio.findall(".//packagedElement", ns):
        etype = el.get(f"{{{ns['xmi']}}}type")
        if etype not in ['uml:Class', 'uml:Enumeration', 'uml:PrimitiveType']: continue
        
        eid = el.get(f"{{{ns['xmi']}}}id")
        ename = el.get("name")
        
        # Ignorar si es el mismo que el root (evitar duplicados)
        if ename == "Thing": continue

        final_type = 'uml:Class' if etype == 'uml:PrimitiveType' and el.find("./ownedAttribute", ns) is not None else etype
        if etype == 'uml:PrimitiveType' and final_type != 'uml:Class': final_type = 'uml:DataType'

        ea_element = ET.SubElement(elements, "element", {
            f"{{{NAMESPACE_XMI_OUTPUT}}}type": final_type,
            f"{{{NAMESPACE_XMI_OUTPUT}}}idref": eid,
            "name": f"{PREFIJO}{ename}"
        })
        props = ET.SubElement(ea_element, "properties", {"documentation": "Importado de Modelio"})
        if el.get("isAbstract") == "true": props.set("stereotype", "Abstract")

        # ATRIBUTOS
        attr_container = ET.SubElement(ea_element, "attributes")
        for attr in el.findall("./ownedAttribute", ns):
            if attr.get("association"): continue
            aid = attr.get(f"{{{ns['xmi']}}}id")
            aname = attr.get("name")
            ea_attr = ET.SubElement(attr_container, "attribute", {
                f"{{{NAMESPACE_XMI_OUTPUT}}}idref": aid,
                "name": f"{PREFIJO}has{aname[:1].upper() + aname[1:]}" if "Class" in final_type else f"{PREFIJO}{aname}"
            })
            ET.SubElement(ea_attr, "properties", {"type": "xsd:string"}) # Simplificado
            ET.SubElement(ea_attr, "bounds", {"lower": "1", "upper": "1"})

        # --- AUTO-HERENCIA HACIA PRUEBA:THING ---
        # Si es una Clase o Enum y no tiene padre en Modelio, lo colgamos de prueba:Thing
        if not catalog[eid]['has_parent'] and etype in ['uml:Class', 'uml:Enumeration']:
            gen_id = f"gen_{eid}_to_root"
            ea_gen = ET.SubElement(connectors, "connector", {f"{{{NAMESPACE_XMI_OUTPUT}}}idref": gen_id})
            ET.SubElement(ea_gen, "properties", {"ea_type": "Generalization", "direction": "Source -> Destination"})
            ET.SubElement(ET.SubElement(ea_gen, "source", {f"{{{NAMESPACE_XMI_OUTPUT}}}idref": eid}), "model", {"name": f"{PREFIJO}{ename}", "type": "Class"})
            ET.SubElement(ET.SubElement(ea_gen, "target", {f"{{{NAMESPACE_XMI_OUTPUT}}}idref": root_class_id}), "model", {"name": f"{PREFIJO}Thing", "type": "Class"})

    # 2. PROCESAR RESTO DE CONECTORES (ASOCIACIONES)
    for el in root_modelio.findall(".//packagedElement[@xmi:type='uml:Class']", ns):
        sid = el.get(f"{{{ns['xmi']}}}id")
        for attr in el.findall("./ownedAttribute[@association]", ns):
            tid = attr.get("type")
            if tid not in catalog: continue
            ea_conn = ET.SubElement(connectors, "connector", {f"{{{NAMESPACE_XMI_OUTPUT}}}idref": attr.get("association")})
            ET.SubElement(ea_conn, "properties", {"ea_type": "Association", "direction": "Source -> Destination"})
            ET.SubElement(ET.SubElement(ea_conn, "source", {f"{{{NAMESPACE_XMI_OUTPUT}}}idref": sid}), "model", {"name": f"{PREFIJO}{catalog[sid]['name']}", "type": "Class"})
            tgt = ET.SubElement(ea_conn, "target", {f"{{{NAMESPACE_XMI_OUTPUT}}}idref": tid})
            ET.SubElement(tgt, "model", {"name": f"{PREFIJO}{catalog[tid]['name']}", "type": catalog[tid]['type']})
            ET.SubElement(tgt, "role", {"name": f"{PREFIJO}has{attr.get('name')[:1].upper() + attr.get('name')[1:]}", "visibility": "Public"})

    # 3. GENERALIZACIONES EXISTENTES (HERENCIA DE MODELIO)
    for gen in root_modelio.findall(".//generalization", ns):
        parent_el = root_modelio.find(f".//*[@xmi:id='{gen.get(f'{{{ns['xmi']}}}id')}']/..", ns)
        if parent_el is None: continue
        sid = parent_el.get(f"{{{ns['xmi']}}}id")
        tid = gen.get("general")
        if sid and tid and sid in catalog and tid in catalog:
            ea_gen = ET.SubElement(connectors, "connector", {f"{{{NAMESPACE_XMI_OUTPUT}}}idref": gen.get(f"{{{ns['xmi']}}}id")})
            ET.SubElement(ea_gen, "properties", {"ea_type": "Generalization", "direction": "Source -> Destination"})
            ET.SubElement(ET.SubElement(ea_gen, "source", {f"{{{NAMESPACE_XMI_OUTPUT}}}idref": sid}), "model", {"name": f"{PREFIJO}{catalog[sid]['name']}", "type": "Class"})
            ET.SubElement(ET.SubElement(ea_gen, "target", {f"{{{NAMESPACE_XMI_OUTPUT}}}idref": tid}), "model", {"name": f"{PREFIJO}{catalog[tid]['name']}", "type": "Class"})

    tree_ea = ET.ElementTree(root_ea)
    tree_ea.write(output_file, encoding="UTF-8", xml_declaration=True)

if __name__ == "__main__":
    adaptar_modelio_a_ea(sys.argv[1], sys.argv[2])