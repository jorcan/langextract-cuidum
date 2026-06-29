"""
Pydantic schemas for phonecall entity extraction.
~100 entities across 10 categories: Contexto, Salud, Economico, Relacional,
Operativo, Comunicacion, and Predictivas.
"""

from pydantic import BaseModel, Field
from typing import Optional


class CallMetadata(BaseModel):
    """Metadata about the call itself."""
    call_id: int
    partner_id: Optional[int] = None
    call_date: Optional[str] = None
    clave: Optional[int] = None
    subclave: Optional[int] = None


class CallEntities(BaseModel):
    """
    Entities extracted from a phonecall transcription.

    ~100 fields across 7 categories + general fields:
      A. Contexto          — who, where, what service
      B. Salud             — health & clinical status
      C. Economico         — financial situation
      D. Relacional        — relationships & emotions
      E. Operativo         — logistics & scheduling
      F. Comunicacion      — call dynamics & tone
      G. Predictivas       — churn risk & business signals

    Version: 2.0.0
    """

    # ── General / Legacy fields ──────────────────────────────────────────────
    problema_reportado: Optional[str] = Field(
        None,
        description="Motivo principal o problema que originó la llamada. "
                    "Ej: 'La cuidadora llegó tarde', 'Problema con la factura', "
                    "'Quiero cambiar de cuidadora'"
    )
    urgencia: Optional[str] = Field(
        None,
        description="Nivel de urgencia de la llamada.",
        pattern=r"^(rutinario|urgente|crítico)$"
    )
    resolucion: Optional[str] = Field(
        None,
        description="Cómo se resolvió o quedó la llamada. "
                    "Ej: 'Se envía email con presupuesto', "
                    "'Queda en llamar más tarde', 'Se programa visita'"
    )
    temas_clave: Optional[list[str]] = Field(
        None,
        description="Lista de temas clave tratados en la llamada. "
                    "Ej: ['renovación', 'horarios', 'pago', 'sustitución']"
    )
    menciona_baja: Optional[bool] = Field(
        None,
        description="True si el interlocutor menciona explícitamente la "
                    "posibilidad de darse de baja o cancelar el servicio."
    )
    menciona_queja: Optional[bool] = Field(
        None,
        description="True si hay una queja explícita sobre el servicio, "
                    "la cuidadora, la facturación o cualquier aspecto."
    )
    necesidad_especifica: Optional[str] = Field(
        None,
        description="Necesidad concreta expresada. "
                    "Ej: 'Necesito alguien que hable inglés', "
                    "'Solo por las mañanas', 'Necesito factura con CIF'"
    )

    # ════════════════════════════════════════════════════════════════════════
    # A. CONTEXTO — Who, where, what service
    # ════════════════════════════════════════════════════════════════════════
    quien_llama: Optional[str] = Field(
        None,
        description="Persona que realiza la llamada: 'familiar', 'paciente', "
                    "'cuidadora', 'tutor_legal', 'otro'."
    )
    relacion_llamante_paciente: Optional[str] = Field(
        None,
        description="Relación del llamante con el paciente. "
                    "Ej: 'hijo/a', 'cónyuge', 'hermano/a', 'ella_misma', "
                    "'cuidadora_contratada'."
    )
    ubicacion_servicio: Optional[str] = Field(
        None,
        description="Ubicación donde se presta el servicio. "
                    "Ej: 'domicilio_paciente', 'residencia', 'hospital', "
                    "'domicilio_familiar'."
    )
    tipo_vivienda_acceso: Optional[str] = Field(
        None,
        description="Tipo de vivienda y condiciones de acceso. "
                    "Ej: 'piso_con_ascensor', 'casa_sin_ascensor', "
                    "'piso_sin_ascensor_4°', 'residencia'."
    )
    convivencia_paciente: Optional[str] = Field(
        None,
        description="Con quién convive el paciente. "
                    "Ej: 'solo', 'con_conyuge', 'con_hijos', "
                    "'con_cuidadora_interna', 'residencia'."
    )
    personas_en_casa: Optional[str] = Field(
        None,
        description="Personas presentes en el domicilio durante el servicio. "
                    "Ej: 'solo_el_paciente', 'familiar_presente', "
                    "'hay_otra_cuidadora', 'hay_ninos'."
    )
    tipo_servicio_actual: Optional[str] = Field(
        None,
        description="Tipo de servicio contratado actualmente. "
                    "Ej: 'compania', 'aseo_personal', 'cuidados_enfermeria', "
                    "'acompanamiento_medico', 'limpieza', 'mixto'."
    )
    antiguedad_estimada: Optional[str] = Field(
        None,
        description="Antigüedad aproximada del cliente con el servicio. "
                    "Ej: 'nuevo_menos_1_mes', '1_3_meses', '3_6_meses', "
                    "'6_12_meses', 'mas_de_1_ano'."
    )
    num_cuidadoras_historico_inferido: Optional[str] = Field(
        None,
        description="Número de cuidadoras distintas que ha tenido el cliente "
                    "según se infiere de la conversación. "
                    "Ej: 'una_sola', 'dos_tres', 'muchas_rotacion', 'no_menciona'."
    )
    frecuencia_contacto_inferida: Optional[str] = Field(
        None,
        description="Frecuencia con la que el cliente contacta con la empresa. "
                    "Ej: 'primera_llamada', 'contacto_habitual', "
                    "'contacto_frecuente_quejas', 'no_se_infiere'."
    )

    # ════════════════════════════════════════════════════════════════════════
    # B. SALUD — Health & clinical status
    # ════════════════════════════════════════════════════════════════════════
    patologia_principal: Optional[str] = Field(
        None,
        description="Patología principal del paciente mencionada. "
                    "Ej: 'Alzheimer', 'Parkinson', 'ictus', 'diabetes', "
                    '"fractura_cadera", "vejez_debilidad".'
    )
    patologia_severidad: Optional[str] = Field(
        None,
        description="Severidad estimada de la patología principal. "
                    "Ej: 'leve', 'moderada', 'avanzada', 'estadio_terminal', "
                    "'no_mencionada'."
    )
    patologias_secundarias: Optional[list[str]] = Field(
        None,
        description="Lista de patologías secundarias o comorbilidades "
                    "del paciente. Ej: ['hipertensión', 'diabetes tipo 2', "
                    "'artrosis']."
    )
    evolucion_reciente_salud: Optional[str] = Field(
        None,
        description="Evolución reciente del estado de salud. "
                    "Ej: 'estable', 'mejorando', 'empeorando', "
                    "'post_operatorio', 'reciente_diagnostico'."
    )
    movilidad_actual: Optional[str] = Field(
        None,
        description="Nivel de movilidad actual del paciente. "
                    "Ej: 'independiente', 'baston_andador', 'silla_ruedas', "
                    '"encamado", "dependencia_total".'
    )
    continencia: Optional[str] = Field(
        None,
        description="Estado de continencia del paciente. "
                    "Ej: 'continente', 'incontinencia_urinaria', "
                    "'incontinencia_fecal', 'doble_incontinencia', 'no_mencionada'."
    )
    alimentacion: Optional[str] = Field(
        None,
        description="Necesidades o estado de alimentación del paciente. "
                    "Ej: 'independiente', 'asistida_parcial', 'sonda_enteral', "
                    "'alimentacion_triturada', 'dificultad_deglucion'."
    )
    estado_cognitivo: Optional[str] = Field(
        None,
        description="Estado cognitivo del paciente. "
                    "Ej: 'orientado', 'desorientacion_parcial', "
                    "'desorientacion_grave', 'demencia_avanzada', 'no_mencionado'."
    )
    estado_animo_paciente: Optional[str] = Field(
        None,
        description="Estado anímico del paciente según lo descrito. "
                    "Ej: 'animado', 'depresivo', 'apatia', 'ansioso', "
                    "'irritable', 'no_mencionado'."
    )
    historial_caidas: Optional[str] = Field(
        None,
        description="Historial de caídas del paciente. "
                    "Ej: 'caidas_frecuentes', 'caida_reciente', 'sin_caidas', "
                    "'riesgo_caidas_mencionado', 'no_mencionado'."
    )
    hospitalizaciones_recientes: Optional[str] = Field(
        None,
        description="Hospitalizaciones recientes del paciente. "
                    "Ej: 'hospitalizado_ultimo_mes', 'alta_reciente', "
                    '"ingreso_programado", "sin_hospitalizaciones", '
                    "'no_mencionado'."
    )
    medicacion_complejidad: Optional[str] = Field(
        None,
        description="Complejidad de la medicación del paciente. "
                    "Ej: 'simple_pocos_farmacos', 'compleja_multiples', "
                    "'cambio_reciente_medicacion', 'inyectable', 'no_mencionada'."
    )
    necesita_rehabilitacion: Optional[bool] = Field(
        None,
        description="True si el paciente necesita o está recibiendo "
                    "rehabilitación (fisioterapia, logopedia, etc.)."
    )
    calidad_suenio: Optional[str] = Field(
        None,
        description="Calidad del sueño del paciente. "
                    "Ej: 'buena', 'regular_insomnio', 'despertares_nocturnos', "
                    "'somnilencia_diurna', 'no_mencionada'."
    )
    apetito_nutricion: Optional[str] = Field(
        None,
        description="Estado del apetito y nutrición del paciente. "
                    "Ej: 'normal', 'poco_apetito', 'perdida_peso', "
                    "'hidratacion_insuficiente', 'no_mencionado'."
    )
    dolor_cronico: Optional[str] = Field(
        None,
        description="Presencia y descripción del dolor crónico. "
                    "Ej: 'dolor_leve_controlado', 'dolor_moderado_persistente', "
                    "'dolor_severo_no_controlado', 'no_mencionado'."
    )
    riesgo_ulceras: Optional[bool] = Field(
        None,
        description="True si hay riesgo mencionado de úlceras por presión "
                    "o el paciente ya las tiene."
    )
    alergias_intolerancias: Optional[list[str]] = Field(
        None,
        description="Lista de alergias o intolerancias del paciente. "
                    "Ej: ['lactosa', 'gluten', 'alergia_medicamentosa']."
    )
    necesidades_no_cubiertas: Optional[list[str]] = Field(
        None,
        description="Necesidades de salud que el cliente menciona que no "
                    "están siendo cubiertas. "
                    "Ej: ['falta_fisioterapia', 'necesita_enfermera', "
                    "'necesita_logopeda']."
    )
    derivacion_medica: Optional[str] = Field(
        None,
        description="Derivación médica mencionada o necesaria. "
                    "Ej: 'pendiente_valoracion_neurologo', "
                    "'derivado_a_urgencias', 'pendiente_cita_medico', "
                    "'no_mencionada'."
    )

    # ════════════════════════════════════════════════════════════════════════
    # C. ECONOMICO — Financial situation & billing
    # ════════════════════════════════════════════════════════════════════════
    situacion_pagos: Optional[str] = Field(
        None,
        description="Situación de los pagos del cliente. "
                    "Ej: 'al_dia', 'pendiente_ultimo_mes', 'adeuda_varios_meses', "
                    "'problemas_pago_recurrentes', 'no_mencionada'."
    )
    metodo_pago: Optional[str] = Field(
        None,
        description="Método de pago usado o preferido. "
                    "Ej: 'transferencia', 'tarjeta', 'domiciliacion', "
                    "'efectivo', 'bizum', 'no_mencionado'."
    )
    queja_precio_intensidad: Optional[str] = Field(
        None,
        description="Intensidad de la queja sobre el precio o relación "
                    "calidad-precio. "
                    "Ej: 'sin_queja', 'leve_mencion_caro', 'queja_explicita', "
                    "'amenaza_baja_por_precio', 'renegociacion_exitosa'."
    )
    negociacion_tarifa: Optional[bool] = Field(
        None,
        description="True si el cliente solicita explícitamente negociar "
                    "la tarifa o pide un descuento."
    )
    pension_ingresos_mencionados: Optional[str] = Field(
        None,
        description="Mención de pensión, ingresos o situación económica. "
                    "Ej: 'pension_no_contributiva', 'pension_contributiva_baja', "
                    "'ingresos_familiares_medios', 'dificultad_economica', "
                    "'no_mencionado'."
    )
    subvenciones: Optional[str] = Field(
        None,
        description="Subvenciones o ayudas mencionadas. "
                    "Ej: 'ley_dependencia', 'ayuda_municipal', 'seguro_privado', "
                    "'no_mencionada'."
    )
    ampliacion_horas_interes: Optional[bool] = Field(
        None,
        description="True si el cliente muestra interés en ampliar las horas "
                    "del servicio (upsell opportunity)."
    )
    reduccion_horas_riesgo: Optional[bool] = Field(
        None,
        description="True si el cliente sugiere o amenaza con reducir horas "
                    "del servicio (downgrade risk)."
    )
    servicios_extra_solicitados: Optional[list[str]] = Field(
        None,
        description="Lista de servicios adicionales solicitados por el cliente. "
                    "Ej: ['fisioterapia', 'compania_nocturna', "
                    "'cuidados_enfermeria', 'limpieza_profunda']."
    )
    tipo_contrato: Optional[str] = Field(
        None,
        description="Tipo de contrato del cliente. "
                    "Ej: 'particular', 'seguro_privado', 'servicio_publico', "
                    "'mutualidad', 'no_mencionado'."
    )
    confianza_economica: Optional[str] = Field(
        None,
        description="Confianza del cliente en la gestión económica. "
                    "Ej: 'confianza_total', 'dudas_facturas', "
                    "'reclamacion_factura', 'desconfianza_explicita', "
                    "'no_mencionada'."
    )
    intencion_permanencia: Optional[str] = Field(
        None,
        description="Intención del cliente de permanecer en el servicio "
                    "desde perspectiva económica. "
                    "Ej: 'seguro_permanece', 'dudas_economicas', "
                    "'probable_baja_por_precio', 'buscando_alternativas', "
                    "'no_se_infiere'."
    )

    # ════════════════════════════════════════════════════════════════════════
    # D. RELACIONAL — Relationships, emotions & satisfaction
    # ════════════════════════════════════════════════════════════════════════
    vinculo_cuidadora_paciente: Optional[str] = Field(
        None,
        description="Vínculo entre la cuidadora actual y el paciente. "
                    "Ej: 'excelente_afecto', 'bueno_profesional', "
                    "'tenso_conflictivo', 'indiferente', 'no_mencionado'."
    )
    vinculo_cuidadora_familia: Optional[str] = Field(
        None,
        description="Vínculo entre la cuidadora y la familia. "
                    "Ej: 'muy_buena_relacion', 'relacion_distante', "
                    "'conflicto_explicito', 'no_mencionado'."
    )
    satisfaccion_general: Optional[float] = Field(
        None,
        description="Satisfacción general del cliente valorada de 0 a 10. "
                    "Ej: 8.5 para muy satisfecho, 2.0 para muy insatisfecho.",
        ge=0.0,
        le=10.0
    )
    sentimiento_apertura: Optional[str] = Field(
        None,
        description="Sentimiento o emoción predominante al inicio de la "
                    "llamada. "
                    "Ej: 'cordial', 'neutro', 'tenso', 'frustrado', "
                    "'urgente', 'agradecido'."
    )
    sentimiento_cierre: Optional[str] = Field(
        None,
        description="Sentimiento o emoción predominante al final de la "
                    "llamada. "
                    "Ej: 'satisfecho', 'aliviado', 'aun_frustrado', "
                    "'indiferente', 'agradecido', 'molesto'."
    )
    tendencia_emocional_llamada: Optional[str] = Field(
        None,
        description="Evolución emocional durante la llamada. "
                    "Ej: 'mejora_tras_gestion', 'empeora_por_respuesta', "
                    "'se_mantiene_positiva', 'se_mantiene_negativa', "
                    "'volatil_cambios_bruscos'."
    )
    estres_cuidador_familiar: Optional[str] = Field(
        None,
        description="Nivel de estrés del cuidador familiar. "
                    "Ej: 'sin_estres_aparente', 'estres_moderado', "
                    "'estres_alto_agotamiento', 'sindrome_cuidador', "
                    "'no_aplica'."
    )
    apoyo_familiar: Optional[str] = Field(
        None,
        description="Nivel de apoyo familiar en el cuidado. "
                    "Ej: 'familia_implicada', 'apoyo_parcial', "
                    "'sin_apoyo_familiar', 'conflicto_familiar_cuidado', "
                    "'no_mencionado'."
    )
    conflictos_familiares: Optional[str] = Field(
        None,
        description="Conflictos familiares mencionados relacionados "
                    "con el cuidado. "
                    "Ej: 'desacuerdo_horarios', 'disputa_economica', "
                    '"desacuerdo_tratamiento", "sin_conflictos", '
                    "'no_mencionados'."
    )
    confianza_empresa: Optional[str] = Field(
        None,
        description="Confianza del cliente en la empresa. "
                    "Ej: 'alta', 'media', 'baja_desconfianza', "
                    "'traicionada_por_incidente', 'no_mencionada'."
    )
    lealtad_marca: Optional[str] = Field(
        None,
        description="Nivel de lealtad del cliente hacia la marca. "
                    "Ej: 'defensor_promotor', 'cliente_fiel_pasivo', "
                    "'cliente_riesgo_cambio', 'busca_activamente_alternativas', "
                    "'no_se_infiere'."
    )
    menciona_competidores: Optional[list[str]] = Field(
        None,
        description="Lista de competidores mencionados por el cliente. "
                    "Ej: ['Atenzia', 'Sanyres', 'Clece', 'Mimo']."
    )
    probabilidad_recomendacion: Optional[str] = Field(
        None,
        description="Probabilidad inferida de que el cliente recomiende "
                    "el servicio. "
                    "Ej: 'alta', 'media', 'baja', 'no_se_infiere'."
    )
    frustracion_acumulada: Optional[str] = Field(
        None,
        description="Nivel de frustración acumulada del cliente. "
                    "Ej: 'sin_frustracion', 'leve_incidencias_puntuales', "
                    "'frustracion_acumulada_visible', "
                    "'cliente_al_limite_explosion'."
    )
    evento_vital: Optional[str] = Field(
        None,
        description="Evento vital significativo mencionado. "
                    "Ej: 'fallecimiento_conyuge', 'nacimiento_nieto', "
                    '"cambio_domicilio", "ingreso_residencia", '
                    "'empeoramiento_diagnostico', 'ninguno_mencionado'."
    )
    soledad_aislamiento: Optional[bool] = Field(
        None,
        description="True si se menciona sentimiento de soledad o "
                    "aislamiento social del paciente o familiar."
    )
    agradecimiento_cliente: Optional[bool] = Field(
        None,
        description="True si el cliente expresa agradecimiento explícito "
                    "hacia la empresa, gestor o cuidadora."
    )
    empatia_gestor: Optional[bool] = Field(
        None,
        description="True si el gestor muestra empatía explícita durante "
                    "la llamada (validar sentimientos, disculparse, "
                    "mostrar comprensión)."
    )

    # ════════════════════════════════════════════════════════════════════════
    # E. OPERATIVO — Logistics, scheduling & service delivery
    # ════════════════════════════════════════════════════════════════════════
    cambios_horario_frecuencia: Optional[str] = Field(
        None,
        description="Frecuencia de cambios de horario solicitados. "
                    "Ej: 'sin_cambios', 'cambio_puntual', 'cambios_recurrentes', "
                    "'reprogramacion_constante'."
    )
    cancelaciones_ratio_sugerido: Optional[str] = Field(
        None,
        description="Ratio de cancelaciones sugerido por el discurso. "
                    "Ej: 'nunca_cancela', 'cancela_ocasionalmente', "
                    "'cancela_a_menudo', 'no_se_infiere'."
    )
    solicitudes_ultima_hora: Optional[bool] = Field(
        None,
        description="True si el cliente hace solicitudes de última hora "
                    "que afectan la planificación."
    )
    problemas_transporte: Optional[str] = Field(
        None,
        description="Problemas de transporte de la cuidadora para llegar "
                    "al domicilio. "
                    "Ej: 'acceso_transporte_publico', 'dificultad_aparcamiento', "
                    '"lejania_domicilio", "sin_problemas", "no_mencionados".'
    )
    problemas_acceso_vivienda: Optional[str] = Field(
        None,
        description="Problemas de acceso a la vivienda. "
                    "Ej: 'portero_automatico', 'escaleras_sin_ascensor', "
                    "'llaves_no_disponibles', 'mascota_suelta', 'sin_problemas'."
    )
    mascotas_en_domicilio: Optional[str] = Field(
        None,
        description="Presencia de mascotas en el domicilio. "
                    "Ej: 'perro', 'gato', 'varias_mascotas', "
                    '"sin_mascotas", "no_mencionado".'
    )
    incidencias_repetitivas: Optional[list[str]] = Field(
        None,
        description="Lista de incidencias que se repiten en el servicio. "
                    "Ej: ['retrasos_frecuentes', 'faltas_aviso', "
                    "'material_no_entregado', 'horario_no_respetado']."
    )
    rotacion_cuidadoras_explicita: Optional[str] = Field(
        None,
        description="Mención explícita de rotación de cuidadoras. "
                    "Ej: 'misma_siempre', 'rotacion_normal', "
                    "'mucha_rotacion_queja', 'ha_cambiado_varias_veces', "
                    "'no_mencionada'."
    )
    disponibilidad_real_horaria: Optional[str] = Field(
        None,
        description="Disponibilidad horaria real del cliente o paciente. "
                    "Ej: 'horario_fijo_manana', 'horario_fijo_tarde', "
                    "'horario_variable', 'disponibilidad_total', 'no_mencionada'."
    )
    necesidad_festivos: Optional[str] = Field(
        None,
        description="Necesidad de cobertura en festivos o fines de semana. "
                    "Ej: 'necesita_festivos_si', 'no_necesita_festivos', "
                    "'necesita_fines_semana', 'duda_sobre_festivos', "
                    "'no_mencionada'."
    )
    barreras_logisticas: Optional[list[str]] = Field(
        None,
        description="Lista de barreras logísticas generales. "
                    "Ej: ['zona_mala_conexion', 'no_coche_cuidadora', "
                    "'zona_inundacion', 'carretera_complicada_invierno']."
    )
    problemas_material_equipamiento: Optional[list[str]] = Field(
        None,
        description="Lista de problemas con material o equipamiento. "
                    "Ej: ['falta_panales', 'cama_articulada_no_disponible', "
                    "'silla_ruedas_rota', 'falta_material_cura']."
    )

    # ════════════════════════════════════════════════════════════════════════
    # F. COMUNICACION — Call dynamics & communication style
    # ════════════════════════════════════════════════════════════════════════
    canal_comunicacion: Optional[str] = Field(
        None,
        description="Canal por el que se recibe la llamada. "
                    "Ej: 'telefono_entrante', 'telefono_saliente', "
                    "'email_derivado', 'whatsapp_derivado', 'no_mencionado'."
    )
    duracion_llamada_minutos: Optional[float] = Field(
        None,
        description="Duración estimada de la llamada en minutos.",
        ge=0.0
    )
    claridad_comunicacion: Optional[str] = Field(
        None,
        description="Claridad con la que el interlocutor se expresa. "
                    "Ej: 'clara_fluida', 'algo_confusa_vaguedad', "
                    "'muy_confusa_contradicciones', 'no_se_infiere'."
    )
    nivel_exigencia: Optional[str] = Field(
        None,
        description="Nivel de exigencia del cliente durante la llamada. "
                    "Ej: 'bajo', 'moderado_razonable', 'alto_exigente', "
                    '"muy_alto_irrazonable", "no_se_infiere".'
    )
    actitud_cliente: Optional[str] = Field(
        None,
        description="Actitud general del cliente en la llamada. "
                    "Ej: 'colaborativa', 'pasiva', 'exigente', 'hostil', "
                    "'agradecida', 'desconfiada', 'indiferente'."
    )
    coherencia_relato: Optional[str] = Field(
        None,
        description="Coherencia del relato del cliente. "
                    "Ej: 'coherente', 'parcialmente_contradictorio', "
                    "'contradicciones_importantes', 'no_se_infiere'."
    )
    receptividad_gestion: Optional[str] = Field(
        None,
        description="Receptividad del cliente a las soluciones propuestas "
                    "por el gestor. "
                    "Ej: 'acepta_de_inmediato', 'acepta_tras_dudas', "
                    "'rechaza_alternativas', 'no_se_propone_gestion', "
                    "'no_se_infiere'."
    )
    urgencia_voz_tono: Optional[str] = Field(
        None,
        description="Urgencia percibida en el tono de voz del interlocutor. "
                    "Ej: 'tono_tranquilo', 'tono_preocupado', "
                    "'tono_angustiado', 'tono_agresivo', 'tono_llanto', "
                    "'no_se_infiere'."
    )

    # ════════════════════════════════════════════════════════════════════════
    # G. PREDICTIVAS — Churn risk & business intelligence signals
    # ════════════════════════════════════════════════════════════════════════
    churn_risk_score: Optional[float] = Field(
        None,
        description="Riesgo de churn general estimado de 0 a 1. "
                    "0 = mínimo riesgo, 1 = abandono inminente.",
        ge=0.0,
        le=1.0
    )
    baja_probabilidad_inferida: Optional[float] = Field(
        None,
        description="Probabilidad inferida de baja del servicio de 0 a 1.",
        ge=0.0,
        le=1.0
    )
    menciona_competidores_lista: Optional[list[str]] = Field(
        None,
        description="Lista de competidores que el cliente menciona haber "
                    "contactado o estar considerando. "
                    "Ej: ['Atenzia', 'Clece']."
    )
    frustracion_acumulada_tendencia: Optional[str] = Field(
        None,
        description="Tendencia de la frustración acumulada en el tiempo. "
                    "Ej: 'estable_baja', 'en_aumento_preocupante', "
                    "'estallido_reciente', 'en_descenso_mejoria', 'no_se_infiere'."
    )
    deseo_cambio_cuidadora: Optional[bool] = Field(
        None,
        description="True si el cliente expresa deseo explícito de cambiar "
                    "de cuidadora."
    )
    umbral_paciencia_cliente: Optional[str] = Field(
        None,
        description="Estado del umbral de paciencia del cliente. "
                    "Ej: 'paciente_tolerante', 'paciencia_gastandose', "
                    "'al_limite_ultima_oportunidad', 'sin_paciencia_actuara', "
                    "'no_se_infiere'."
    )
    fase_ciclo_cliente_inferida: Optional[str] = Field(
        None,
        description="Fase del ciclo de vida del cliente inferida. "
                    "Ej: 'onboarding', 'estable', 'riesgo_baja', "
                    "'recuperacion_tras_incidencia', 'salida_programada', "
                    "'no_se_infiere'."
    )
    downgrade_risk: Optional[bool] = Field(
        None,
        description="True si hay indicios de que el cliente reducirá horas "
                    "o servicios contratados."
    )
    upsell_opportunity: Optional[bool] = Field(
        None,
        description="True si hay indicios de que el cliente podría ampliar "
                    "horas o contratar servicios adicionales."
    )
    anomalia_comportamiento: Optional[bool] = Field(
        None,
        description="True si se detecta un comportamiento anómalo respecto "
                    "al patrón histórico del cliente (nunca llamaba y ahora sí, "
                    "cambio brusco de tono, etc.)."
    )
    mejora_salud_implica_baja: Optional[bool] = Field(
        None,
        description="True si la mejora de salud del paciente implica riesgo "
                    "de reducción o baja del servicio."
    )
    amenaza_reclamacion_legal: Optional[bool] = Field(
        None,
        description="True si el cliente amenaza con acciones legales, "
                    "reclamación formal o abogado."
    )
    ventana_abandono_estimada_dias: Optional[int] = Field(
        None,
        description="Estimación en días del plazo probable de abandono "
                    "del servicio si no se interviene. Null si no aplica.",
        ge=1
    )
    proxima_necesidad_predicha: Optional[str] = Field(
        None,
        description="Predicción de la próxima necesidad del cliente. "
                    "Ej: 'solicitara_aumento_horas', 'pedira_cambio_cuidadora', "
                    "'reclamara_factura_pendiente', 'contactara_competencia', "
                    '"dara_baja", "no_mantenimiento_sin_cambios".'
    )
    discrepancia_datos_odoo: Optional[list[str]] = Field(
        None,
        description="Lista de discrepancias detectadas entre lo que dice el "
                    "cliente y los datos en Odoo. "
                    "Ej: ['horario_no_coincide', 'cuidadora_asignada_no_es_actual', "
                    "'direccion_diferente', 'tarifa_diferente']."
    )


class ExtractionResult(BaseModel):
    """Complete extraction result for one phonecall."""
    call: CallMetadata
    entities: CallEntities
    confidence: float = Field(
        1.0,
        description="Confianza general de la extracción (0-1)",
        ge=0.0,
        le=1.0
    )
    schema_version: str = "2.0.0"
    raw_text_preview: Optional[str] = None


# =====================================================================
# EXTRACTION PROMPT
# =====================================================================

EXTRACTION_PROMPT = """Eres un asistente especializado en extraer información estructurada de transcripciones de llamadas de un servicio de ayuda a domicilio (Cuidum).

Las llamadas son entre gestores de Cuidum y clientes (familias que contratan cuidadores) o cuidadoras.

Extrae hasta ~100 campos organizados en las siguientes categorías. Responde ÚNICAMENTE con un objeto JSON válido siguiendo la estructura que se detalla abajo. Todos los campos opcionales deben ser null si no encuentras evidencia textual explícita. No inventes información.

─── CATEGORÍAS ───

1. GENERALES
- problema_reportado: Motivo principal de la llamada (texto breve).
- urgencia: "rutinario" | "urgente" | "crítico"
- resolucion: Cómo se resolvió o quedó la llamada.
- temas_clave: Lista de temas tratados.
- menciona_baja: true/false — ¿menciona explícitamente darse de baja?
- menciona_queja: true/false — ¿hay queja explícita?
- necesidad_especifica: Necesidad concreta expresada.

2. CONTEXTO (A)
- quien_llama: "familiar" | "paciente" | "cuidadora" | "tutor_legal" | "otro"
- relacion_llamante_paciente: Relación del que llama con el paciente.
- ubicacion_servicio: Dónde se presta el servicio.
- tipo_vivienda_acceso: Tipo de vivienda y acceso.
- convivencia_paciente: Con quién convive el paciente.
- personas_en_casa: Quién más está durante el servicio.
- tipo_servicio_actual: Tipo de servicio contratado.
- antiguedad_estimada: Cuánto tiempo lleva el cliente.
- num_cuidadoras_historico_inferido: Cuántas cuidadoras distintas ha tenido.
- frecuencia_contacto_inferida: Frecuencia con que contacta.

3. SALUD (B)
- patologia_principal: Diagnóstico principal.
- patologia_severidad: "leve" | "moderada" | "avanzada" | "estadio_terminal" | "no_mencionada"
- patologias_secundarias: Lista de comorbilidades.
- evolucion_reciente_salud: "estable" | "mejorando" | "empeorando" | etc.
- movilidad_actual: Nivel de movilidad.
- continencia: Estado de continencia.
- alimentacion: Necesidades alimentarias.
- estado_cognitivo: Nivel cognitivo.
- estado_animo_paciente: Ánimo del paciente.
- historial_caidas: Si ha tenido caídas.
- hospitalizaciones_recientes: Si ha estado hospitalizado.
- medicacion_complejidad: Complejidad de la medicación.
- necesita_rehabilitacion: bool
- calidad_suenio: Calidad del sueño.
- apetito_nutricion: Apetito y estado nutricional.
- dolor_cronico: Presencia de dolor.
- riesgo_ulceras: bool
- alergias_intolerancias: Lista de alergias.
- necesidades_no_cubiertas: Lista de necesidades insatisfechas.
- derivacion_medica: Derivación necesaria.

4. ECONÓMICO (C)
- situacion_pagos: Estado de pagos.
- metodo_pago: Método de pago.
- queja_precio_intensidad: Nivel de queja sobre precio.
- negociacion_tarifa: bool — ¿pide descuento?
- pension_ingresos_mencionados: Mención de ingresos.
- subvenciones: Ayudas o subvenciones.
- ampliacion_horas_interes: bool — ¿quiere más horas?
- reduccion_horas_riesgo: bool — ¿quiere menos horas?
- servicios_extra_solicitados: Lista de servicios extra pedidos.
- tipo_contrato: Tipo de contrato.
- confianza_economica: Confianza en gestión económica.
- intencion_permanencia: Intención de quedarse desde perspectiva económica.

5. RELACIONAL (D)
- vinculo_cuidadora_paciente: Relación cuidadora-paciente.
- vinculo_cuidadora_familia: Relación cuidadora-familia.
- satisfaccion_general: float 0-10
- sentimiento_apertura: Emoción al inicio.
- sentimiento_cierre: Emoción al final.
- tendencia_emocional_llamada: Evolución emocional.
- estres_cuidador_familiar: Estrés del cuidador familiar.
- apoyo_familiar: Apoyo de la familia.
- conflictos_familiares: Conflictos relacionados con el cuidado.
- confianza_empresa: Confianza en Cuidum.
- lealtad_marca: Lealtad del cliente.
- menciona_competidores: Lista de competidores.
- probabilidad_recomendacion: "alta" | "media" | "baja"
- frustracion_acumulada: Nivel de frustración acumulada.
- evento_vital: Evento vital relevante.
- soledad_aislamiento: bool
- agradecimiento_cliente: bool
- empatia_gestor: bool

6. OPERATIVO (E)
- cambios_horario_frecuencia: Frecuencia de cambios de horario.
- cancelaciones_ratio_sugerido: Ratio de cancelaciones.
- solicitudes_ultima_hora: bool — ¿pide cambios urgentes?
- problemas_transporte: Problemas de transporte.
- problemas_acceso_vivienda: Problemas de acceso.
- mascotas_en_domicilio: Mascotas presentes.
- incidencias_repetitivas: Lista de incidencias que se repiten.
- rotacion_cuidadoras_explicita: Rotación de cuidadoras.
- disponibilidad_real_horaria: Disponibilidad horaria.
- necesidad_festivos: Cobertura en festivos.
- barreras_logisticas: Lista de barreras logísticas.
- problemas_material_equipamiento: Problemas con material.

7. COMUNICACIÓN (F)
- canal_comunicacion: Canal de la llamada.
- duracion_llamada_minutos: float — duración estimada.
- claridad_comunicacion: Claridad del interlocutor.
- nivel_exigencia: Exigencia del cliente.
- actitud_cliente: Actitud general.
- coherencia_relato: Coherencia del discurso.
- receptividad_gestion: Aceptación de soluciones.
- urgencia_voz_tono: Urgencia percibida en el tono.

8. PREDICTIVAS (G)
- churn_risk_score: float 0-1 — riesgo de abandono general.
- baja_probabilidad_inferida: float 0-1 — probabilidad de baja.
- menciona_competidores_lista: Lista de competidores contactados.
- frustracion_acumulada_tendencia: Tendencia de la frustración.
- deseo_cambio_cuidadora: bool
- umbral_paciencia_cliente: Estado de la paciencia.
- fase_ciclo_cliente_inferida: Fase del ciclo de vida.
- downgrade_risk: bool — ¿riesgo de reducir servicio?
- upsell_opportunity: bool — ¿oportunidad de ampliar?
- anomalia_comportamiento: bool — ¿comportamiento anómalo?
- mejora_salud_implica_baja: bool
- amenaza_reclamacion_legal: bool
- ventana_abandono_estimada_dias: int — días estimados para posible baja.
- proxima_necesidad_predicha: Próxima necesidad predecible.
- discrepancia_datos_odoo: Lista de discrepancias con Odoo.

IMPORTANTE:
- Todos los campos son opcionales. Si no hay evidencia textual, usa null.
- Para booleanos, solo true si hay evidencia textual explícita.
- Para listas, usa lista vacía si no hay elementos.
- Sé preciso: extrae literalmente cuando sea posible.
- Valida que el JSON sea sintácticamente correcto antes de responder.
"""


# =====================================================================
# FEW-SHOT EXAMPLES
# =====================================================================

EXTRACTION_EXAMPLES = [
    {
        "text": (
            "Buenos días, llamaba porque la cuidadora no ha llegado hoy y no me ha "
            "avisado. Ya van dos veces esta semana que llega tarde o no viene. Mi "
            "madre tiene Alzheimer avanzado, está encamada, y necesita cuidados "
            "constantes. La verdad es que estoy harta, si esto sigue así me voy a dar "
            "de baja y busco otra empresa. He hablado con Atenzia y me ofrecen mejor "
            "precio. Además, con lo que pagamos… 500 euros al mes para este servicio "
            "es una vergüenza."
        ),
        "entities": {
            "problema_reportado": "La cuidadora no ha llegado hoy sin avisar. Es la segunda vez esta semana.",
            "urgencia": "urgente",
            "resolucion": "Pendiente de gestión",
            "temas_clave": ["ausencia cuidadora", "falta aviso", "queja", "amenaza baja", "competencia", "precio"],
            "menciona_baja": True,
            "menciona_queja": True,
            "necesidad_especifica": "Necesita una cuidadora puntual y que avise si no puede asistir",
            "quien_llama": "familiar",
            "relacion_llamante_paciente": "hijo/a",
            "ubicacion_servicio": "domicilio_paciente",
            "tipo_vivienda_acceso": "no_mencionado",
            "convivencia_paciente": "solo",
            "personas_en_casa": "solo_el_paciente",
            "tipo_servicio_actual": "cuidados_enfermeria",
            "antiguedad_estimada": "no_mencionada",
            "num_cuidadoras_historico_inferido": "no_menciona",
            "frecuencia_contacto_inferida": "contacto_frecuente_quejas",
            "patologia_principal": "Alzheimer",
            "patologia_severidad": "avanzada",
            "patologias_secundarias": None,
            "evolucion_reciente_salud": "empeorando",
            "movilidad_actual": "encamado",
            "continencia": "no_mencionada",
            "alimentacion": "asistida_parcial",
            "estado_cognitivo": "demencia_avanzada",
            "estado_animo_paciente": "no_mencionado",
            "historial_caidas": "no_mencionado",
            "hospitalizaciones_recientes": "no_mencionado",
            "medicacion_complejidad": "no_mencionada",
            "necesita_rehabilitacion": None,
            "calidad_suenio": "no_mencionada",
            "apetito_nutricion": "no_mencionado",
            "dolor_cronico": "no_mencionado",
            "riesgo_ulceras": None,
            "alergias_intolerancias": None,
            "necesidades_no_cubiertas": ["cuidados_constantes_paciente_encamado"],
            "derivacion_medica": "no_mencionada",
            "situacion_pagos": "al_dia",
            "metodo_pago": "no_mencionado",
            "queja_precio_intensidad": "queja_explicita",
            "negociacion_tarifa": None,
            "pension_ingresos_mencionados": "dificultad_economica",
            "subvenciones": "no_mencionada",
            "ampliacion_horas_interes": None,
            "reduccion_horas_riesgo": None,
            "servicios_extra_solicitados": None,
            "tipo_contrato": "particular",
            "confianza_economica": "desconfianza_explicita",
            "intencion_permanencia": "probable_baja_por_precio",
            "vinculo_cuidadora_paciente": "no_mencionado",
            "vinculo_cuidadora_familia": "tenso_conflictivo",
            "satisfaccion_general": 1.5,
            "sentimiento_apertura": "frustrado",
            "sentimiento_cierre": "aun_frustrado",
            "tendencia_emocional_llamada": "se_mantiene_negativa",
            "estres_cuidador_familiar": "estres_alto_agotamiento",
            "apoyo_familiar": "sin_apoyo_familiar",
            "conflictos_familiares": "no_mencionados",
            "confianza_empresa": "baja_desconfianza",
            "lealtad_marca": "busca_activamente_alternativas",
            "menciona_competidores": ["Atenzia"],
            "probabilidad_recomendacion": "baja",
            "frustracion_acumulada": "frustracion_acumulada_visible",
            "evento_vital": "ninguno_mencionado",
            "soledad_aislamiento": True,
            "agradecimiento_cliente": False,
            "empatia_gestor": True,
            "cambios_horario_frecuencia": "sin_cambios",
            "cancelaciones_ratio_sugerido": "no_se_infiere",
            "solicitudes_ultima_hora": False,
            "problemas_transporte": "no_mencionados",
            "problemas_acceso_vivienda": "sin_problemas",
            "mascotas_en_domicilio": "no_mencionado",
            "incidencias_repetitivas": ["retrasos_frecuentes", "faltas_aviso"],
            "rotacion_cuidadoras_explicita": "mucha_rotacion_queja",
            "disponibilidad_real_horaria": "horario_fijo_manana",
            "necesidad_festivos": "no_mencionada",
            "barreras_logisticas": None,
            "problemas_material_equipamiento": None,
            "canal_comunicacion": "telefono_entrante",
            "duracion_llamada_minutos": 8.5,
            "claridad_comunicacion": "clara_fluida",
            "nivel_exigencia": "alto_exigente",
            "actitud_cliente": "hostil",
            "coherencia_relato": "coherente",
            "receptividad_gestion": "no_se_propone_gestion",
            "urgencia_voz_tono": "tono_preocupado",
            "churn_risk_score": 0.85,
            "baja_probabilidad_inferida": 0.9,
            "menciona_competidores_lista": ["Atenzia"],
            "frustracion_acumulada_tendencia": "en_aumento_preocupante",
            "deseo_cambio_cuidadora": True,
            "umbral_paciencia_cliente": "al_limite_ultima_oportunidad",
            "fase_ciclo_cliente_inferida": "riesgo_baja",
            "downgrade_risk": False,
            "upsell_opportunity": False,
            "anomalia_comportamiento": False,
            "mejora_salud_implica_baja": False,
            "amenaza_reclamacion_legal": False,
            "ventana_abandono_estimada_dias": 7,
            "proxima_necesidad_predicha": "dara_baja",
            "discrepancia_datos_odoo": None
        }
    },
    {
        "text": (
            "Hola, buenas tardes. Llamaba para agradeceros. La nueva cuidadora, María, "
            "es un encanto. Mi padre está mucho más animado desde que viene ella. Tiene "
            "Parkinson en fase moderada y antes estaba muy apagado, pero ahora hasta "
            "bromea. Me gustaría saber si podría venir también los sábados por la mañana "
            "para que yo pueda hacer recados. El pago lo tengo domiciliado y todo en orden. "
            "Ah, y mi hermana está contenta también, porque antes había mucha tensión con "
            "la cuidadora anterior. Esto es un respiro para toda la familia."
        ),
        "entities": {
            "problema_reportado": "Solicitud de ampliación de horario los sábados",
            "urgencia": "rutinario",
            "resolucion": "Se tramita la solicitud de ampliación para los sábados",
            "temas_clave": ["agradecimiento", "ampliacion horario", "satisfaccion", "nueva cuidadora"],
            "menciona_baja": False,
            "menciona_queja": False,
            "necesidad_especifica": "Necesita que la cuidadora venga los sábados por la mañana",
            "quien_llama": "familiar",
            "relacion_llamante_paciente": "hijo/a",
            "ubicacion_servicio": "domicilio_paciente",
            "tipo_vivienda_acceso": "no_mencionado",
            "convivencia_paciente": "solo",
            "personas_en_casa": "solo_el_paciente",
            "tipo_servicio_actual": "compania",
            "antiguedad_estimada": "no_mencionada",
            "num_cuidadoras_historico_inferido": "dos_tres",
            "frecuencia_contacto_inferida": "contacto_habitual",
            "patologia_principal": "Parkinson",
            "patologia_severidad": "moderada",
            "patologias_secundarias": None,
            "evolucion_reciente_salud": "mejorando",
            "movilidad_actual": "baston_andador",
            "continencia": "no_mencionada",
            "alimentacion": "independiente",
            "estado_cognitivo": "orientado",
            "estado_animo_paciente": "animado",
            "historial_caidas": "no_mencionado",
            "hospitalizaciones_recientes": "sin_hospitalizaciones",
            "medicacion_complejidad": "simple_pocos_farmacos",
            "necesita_rehabilitacion": None,
            "calidad_suenio": "no_mencionada",
            "apetito_nutricion": "normal",
            "dolor_cronico": "no_mencionado",
            "riesgo_ulceras": None,
            "alergias_intolerancias": None,
            "necesidades_no_cubiertas": None,
            "derivacion_medica": "no_mencionada",
            "situacion_pagos": "al_dia",
            "metodo_pago": "domiciliacion",
            "queja_precio_intensidad": "sin_queja",
            "negociacion_tarifa": False,
            "pension_ingresos_mencionados": "no_mencionado",
            "subvenciones": "no_mencionada",
            "ampliacion_horas_interes": True,
            "reduccion_horas_riesgo": False,
            "servicios_extra_solicitados": ["compania_sabados"],
            "tipo_contrato": "particular",
            "confianza_economica": "confianza_total",
            "intencion_permanencia": "seguro_permanece",
            "vinculo_cuidadora_paciente": "excelente_afecto",
            "vinculo_cuidadora_familia": "muy_buena_relacion",
            "satisfaccion_general": 9.5,
            "sentimiento_apertura": "cordial",
            "sentimiento_cierre": "satisfecho",
            "tendencia_emocional_llamada": "se_mantiene_positiva",
            "estres_cuidador_familiar": "sin_estres_aparente",
            "apoyo_familiar": "familia_implicada",
            "conflictos_familiares": "sin_conflictos",
            "confianza_empresa": "alta",
            "lealtad_marca": "defensor_promotor",
            "menciona_competidores": None,
            "probabilidad_recomendacion": "alta",
            "frustracion_acumulada": "sin_frustracion",
            "evento_vital": "ninguno_mencionado",
            "soledad_aislamiento": False,
            "agradecimiento_cliente": True,
            "empatia_gestor": True,
            "cambios_horario_frecuencia": "cambio_puntual",
            "cancelaciones_ratio_sugerido": "nunca_cancela",
            "solicitudes_ultima_hora": False,
            "problemas_transporte": "sin_problemas",
            "problemas_acceso_vivienda": "sin_problemas",
            "mascotas_en_domicilio": "no_mencionado",
            "incidencias_repetitivas": None,
            "rotacion_cuidadoras_explicita": "misma_siempre",
            "disponibilidad_real_horaria": "horario_fijo_manana",
            "necesidad_festivos": "necesita_festivos_si",
            "barreras_logisticas": None,
            "problemas_material_equipamiento": None,
            "canal_comunicacion": "telefono_entrante",
            "duracion_llamada_minutos": 4.0,
            "claridad_comunicacion": "clara_fluida",
            "nivel_exigencia": "bajo",
            "actitud_cliente": "colaborativa",
            "coherencia_relato": "coherente",
            "receptividad_gestion": "acepta_de_inmediato",
            "urgencia_voz_tono": "tono_tranquilo",
            "churn_risk_score": 0.05,
            "baja_probabilidad_inferida": 0.05,
            "menciona_competidores_lista": None,
            "frustracion_acumulada_tendencia": "estable_baja",
            "deseo_cambio_cuidadora": False,
            "umbral_paciencia_cliente": "paciente_tolerante",
            "fase_ciclo_cliente_inferida": "estable",
            "downgrade_risk": False,
            "upsell_opportunity": True,
            "anomalia_comportamiento": False,
            "mejora_salud_implica_baja": False,
            "amenaza_reclamacion_legal": False,
            "ventana_abandono_estimada_dias": None,
            "proxima_necesidad_predicha": "solicitara_aumento_horas",
            "discrepancia_datos_odoo": None
        }
    },
    {
        "text": (
            "Mire, llamo porque necesito que alguien venga a cuidar de mi tía por las "
            "noches. Ahora mismo viene una chica por las mañanas, pero mi tía se despierta "
            "mucho, se levanta y ha tenido dos caídas este mes. Tiene demencia, no está "
            "orientada, y es incontinente. Necesita pañales y que le den la cena. "
            "El problema es que el seguro solo cubre 4 horas al día y nos estamos "
            "gastando un dineral en pagar extras. Ya hemos tenido tres cuidadoras distintas "
            "en seis meses y la verdad es que cansa. Estoy pensando en buscar una residencia "
            "si no podemos organizar las noches. La última cuidadora, Laura, era muy buena "
            "pero se fue porque el horario no le venía bien."
        ),
        "entities": {
            "problema_reportado": "Necesita cobertura nocturna para la paciente con caídas frecuentes",
            "urgencia": "urgente",
            "resolucion": "Se ofrece presupuesto para servicio nocturno y se valora disponibilidad",
            "temas_clave": ["caidas nocturnas", "ampliacion servicio", "incontinencia", "rotacion", "residencia", "seguro"],
            "menciona_baja": False,
            "menciona_queja": True,
            "necesidad_especifica": "Necesita cuidadora nocturna para vigilar y asistir a su tía",
            "quien_llama": "familiar",
            "relacion_llamante_paciente": "sobrino/a",
            "ubicacion_servicio": "domicilio_paciente",
            "tipo_vivienda_acceso": "no_mencionado",
            "convivencia_paciente": "solo",
            "personas_en_casa": "solo_el_paciente",
            "tipo_servicio_actual": "compania",
            "antiguedad_estimada": "6_12_meses",
            "num_cuidadoras_historico_inferido": "muchas_rotacion",
            "frecuencia_contacto_inferida": "contacto_habitual",
            "patologia_principal": "demencia",
            "patologia_severidad": "avanzada",
            "patologias_secundarias": ["incontinencia"],
            "evolucion_reciente_salud": "empeorando",
            "movilidad_actual": "independiente_con_riesgo",
            "continencia": "doble_incontinencia",
            "alimentacion": "asistida_parcial",
            "estado_cognitivo": "desorientacion_grave",
            "estado_animo_paciente": "no_mencionado",
            "historial_caidas": "caidas_frecuentes",
            "hospitalizaciones_recientes": "sin_hospitalizaciones",
            "medicacion_complejidad": "no_mencionada",
            "necesita_rehabilitacion": None,
            "calidad_suenio": "despertares_nocturnos",
            "apetito_nutricion": "no_mencionado",
            "dolor_cronico": "no_mencionado",
            "riesgo_ulceras": None,
            "alergias_intolerancias": None,
            "necesidades_no_cubiertas": ["cobertura_nocturna", "panales_no_incluidos"],
            "derivacion_medica": "no_mencionada",
            "situacion_pagos": "al_dia",
            "metodo_pago": "seguro_privado",
            "queja_precio_intensidad": "leve_mencion_caro",
            "negociacion_tarifa": False,
            "pension_ingresos_mencionados": "no_mencionado",
            "subvenciones": "seguro_privado",
            "ampliacion_horas_interes": True,
            "reduccion_horas_riesgo": False,
            "servicios_extra_solicitados": ["cobertura_nocturna", "cena_asistida"],
            "tipo_contrato": "seguro_privado",
            "confianza_economica": "confianza_total",
            "intencion_permanencia": "dudas_economicas",
            "vinculo_cuidadora_paciente": "bueno_profesional",
            "vinculo_cuidadora_familia": "muy_buena_relacion",
            "satisfaccion_general": 6.0,
            "sentimiento_apertura": "neutro",
            "sentimiento_cierre": "esperanzado",
            "tendencia_emocional_llamada": "mejora_tras_gestion",
            "estres_cuidador_familiar": "estres_moderado",
            "apoyo_familiar": "apoyo_parcial",
            "conflictos_familiares": "no_mencionados",
            "confianza_empresa": "media",
            "lealtad_marca": "cliente_fiel_pasivo",
            "menciona_competidores": None,
            "probabilidad_recomendacion": "media",
            "frustracion_acumulada": "leve_incidencias_puntuales",
            "evento_vital": "empeoramiento_diagnostico",
            "soledad_aislamiento": False,
            "agradecimiento_cliente": False,
            "empatia_gestor": True,
            "cambios_horario_frecuencia": "cambios_recurrentes",
            "cancelaciones_ratio_sugerido": "nunca_cancela",
            "solicitudes_ultima_hora": False,
            "problemas_transporte": "no_mencionados",
            "problemas_acceso_vivienda": "no_mencionados",
            "mascotas_en_domicilio": "no_mencionado",
            "incidencias_repetitivas": ["rotacion_cuidadoras"],
            "rotacion_cuidadoras_explicita": "mucha_rotacion_queja",
            "disponibilidad_real_horaria": "horario_fijo_manana",
            "necesidad_festivos": "necesita_festivos_si",
            "barreras_logisticas": None,
            "problemas_material_equipamiento": ["falta_panales"],
            "canal_comunicacion": "telefono_entrante",
            "duracion_llamada_minutos": 12.0,
            "claridad_comunicacion": "clara_fluida",
            "nivel_exigencia": "moderado_razonable",
            "actitud_cliente": "colaborativa",
            "coherencia_relato": "coherente",
            "receptividad_gestion": "acepta_tras_dudas",
            "urgencia_voz_tono": "tono_preocupado",
            "churn_risk_score": 0.55,
            "baja_probabilidad_inferida": 0.4,
            "menciona_competidores_lista": None,
            "frustracion_acumulada_tendencia": "en_aumento_preocupante",
            "deseo_cambio_cuidadora": False,
            "umbral_paciencia_cliente": "paciencia_gastandose",
            "fase_ciclo_cliente_inferida": "riesgo_baja",
            "downgrade_risk": False,
            "upsell_opportunity": True,
            "anomalia_comportamiento": False,
            "mejora_salud_implica_baja": False,
            "amenaza_reclamacion_legal": False,
            "ventana_abandono_estimada_dias": 30,
            "proxima_necesidad_predicha": "solicitara_aumento_horas",
            "discrepancia_datos_odoo": ["horario_no_coincide"]
        }
    }
]
