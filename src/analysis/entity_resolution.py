import uuid

class EventFuser:
    """
    Clase encargada de consolidar entidades de múltiples noticias 
    y determinar si pertenecen al mismo evento periodístico (Entity Resolution).
    """

    def __init__(self):
        pass

    def _normalize_set(self, values_list):
        """Convierte una lista a un set de cadenas en minúscula para facilitar comparaciones."""
        if not values_list:
            return set()
        return set([str(x).lower().strip() for x in values_list])
        
    def _partial_match_names(self, names1, names2):
        """
        Devuelve True si hay alguna coincidencia entre nombres.
        Verifica coincidencias parciales (ej. 'Juan Pérez' empata con 'Juan').
        """
        for n1 in names1:
            for n2 in names2:
                # Si una de las cadenas está contenida en la otra
                if n1 in n2 or n2 in n1:
                    return True
        return False

    def find_or_create_event(self, nueva_noticia_entidades: dict, eventos_historicos: list) -> tuple:
        """
        Compara las entidades detectadas en una nueva noticia con eventos históricos.
        
        Args:
            nueva_noticia_entidades: dict con 'nombres_personas', 'ubicaciones', 'edades'
            eventos_historicos: list de dicts con la misma estructura y un 'event_id'
            
        Returns:
            tuple: (event_id, merged_entities_dict)
        """
        nuevas_edades = self._normalize_set(nueva_noticia_entidades.get('edades', []))
        nuevos_nombres = self._normalize_set(nueva_noticia_entidades.get('nombres_personas', []))
        nuevas_ubicaciones = self._normalize_set(nueva_noticia_entidades.get('ubicaciones', []))
        
        mejor_evento = None
        max_score = 0
        
        for evento in eventos_historicos:
            hist_edades = self._normalize_set(evento.get('edades', []))
            hist_nombres = self._normalize_set(evento.get('nombres_personas', []))
            hist_ubicaciones = self._normalize_set(evento.get('ubicaciones', []))
            
            # Evaluación Lógica (Regla de Negocio)
            match_edades = len(nuevas_edades.intersection(hist_edades)) > 0
            match_ubicaciones = len(nuevas_ubicaciones.intersection(hist_ubicaciones)) > 0
            match_nombres = self._partial_match_names(nuevos_nombres, hist_nombres)
            
            is_strong_match = match_edades and (match_ubicaciones or match_nombres)
            
            if is_strong_match:
                # Sistema de puntuación para desempatar si hay múltiples matches
                score = (2 if match_edades else 0) + (1.5 if match_nombres else 0) + (1 if match_ubicaciones else 0)
                
                if score > max_score:
                    max_score = score
                    mejor_evento = evento
                
        if mejor_evento:
            # Generar datos fusionados (llenando huecos sin duplicar información fundamental)
            # Volvemos a convertir a formato original (title para nombres, etc. se pierde al mezclar lowers, lo manejamos con title())
            merged_nombres = set(mejor_evento.get('nombres_personas', [])).union(nueva_noticia_entidades.get('nombres_personas', []))
            merged_ubicaciones = set(mejor_evento.get('ubicaciones', [])).union(nueva_noticia_entidades.get('ubicaciones', []))
            merged_edades = set(mejor_evento.get('edades', [])).union(nueva_noticia_entidades.get('edades', []))

            merged_event = {
                'event_id': mejor_evento['event_id'],
                'nombres_personas': list(merged_nombres),
                'ubicaciones': list(merged_ubicaciones),
                'edades': list(merged_edades)
            }
            return merged_event['event_id'], merged_event
            
        else:
            # Nuevo Evento
            nuevo_id = str(uuid.uuid4())
            nuevo_evento = {
                'event_id': nuevo_id,
                'nombres_personas': nueva_noticia_entidades.get('nombres_personas', []),
                'ubicaciones': nueva_noticia_entidades.get('ubicaciones', []),
                'edades': nueva_noticia_entidades.get('edades', [])
            }
            return nuevo_id, nuevo_evento


if __name__ == '__main__':
    fuser = EventFuser()

    # Base de datos simulada de Eventos Históricos
    eventos_historicos_falsos = [
        {
            'event_id': 'evt-100',
            'nombres_personas': ['María López', 'Juan'],
            'ubicaciones': ['Ecatepec', 'Edomex'],
            'edades': ['8 años', '10 años']
        },
        {
            'event_id': 'evt-101',
            'nombres_personas': ['Carlos', 'Ana Ruiz'],
            'ubicaciones': ['Monterrey', 'Nuevo León'],
            'edades': ['12 años']
        }
    ]

    print("=== TESTING EVENT FUSER (Entity Resolution) ===\n")

    # CASO 1: Hace Match (Coincide edad "8 años", ubicación "Ecatepec" y coincidencia parcial de nombre "Juan Pérez")
    nueva_noticia_1 = {
        'nombres_personas': ['Juan Pérez', 'Pedro'],  # Juan Pérez matchea parcialmente con 'Juan'
        'ubicaciones': ['Ecatepec de Morelos', 'Ecatepec'],
        'edades': ['8 años', '5 años']                # Coincide en '8 años'
    }

    print("--- CASO 1: Noticia Relacionada a evt-100 ---")
    event_id_1, merged_1 = fuser.find_or_create_event(nueva_noticia_1, eventos_historicos_falsos)
    print(f"ID Retornado: {event_id_1}")
    print(f"Datos Integrados: {merged_1}\n")

    # CASO 2: Sin Match Fuerte (Misma edad pero distinta persona y municipio)
    nueva_noticia_2 = {
        'nombres_personas': ['Sebastián', 'Raúl'],
        'ubicaciones': ['Guadalajara', 'Jalisco'],
        'edades': ['12 años'] # La edad coincide con evt-101, pero nombres y ubicaciones NO.
    }

    print("--- CASO 2: Noticia de evento totalmente distinto ---")
    event_id_2, merged_2 = fuser.find_or_create_event(nueva_noticia_2, eventos_historicos_falsos)
    print(f"ID Retornado: {event_id_2}")
    print(f"Datos Integrados: {merged_2}\n")
