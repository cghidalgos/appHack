#!/usr/bin/env python3
"""
Script para poblar la base de datos con datos de ejemplo
Ejecutar después de que la aplicación esté funcionando
"""
import sqlite3
import os

# Usar la misma configuración que app.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, 'database.db')

def populate_sample_data():
    """Agrega algunos usuarios y historias de ejemplo"""
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        
        # Insertar usuarios de ejemplo
        usuarios_ejemplo = [
            ('Juan Pérez', '12345678'),
            ('María García', '87654321'),
            ('Carlos López', '11223344')
        ]
        
        for nombre, cedula in usuarios_ejemplo:
            try:
                c.execute('INSERT INTO usuarios (nombre, cedula) VALUES (?, ?)', (nombre, cedula))
                print(f"Usuario agregado: {nombre} - {cedula}")
            except sqlite3.IntegrityError:
                print(f"Usuario ya existe: {nombre} - {cedula}")
        
        # Obtener IDs de usuarios para historias de ejemplo
        c.execute('SELECT id, nombre FROM usuarios')
        usuarios = c.fetchall()
        
        # Insertar historias de ejemplo
        for usuario in usuarios[:2]:  # Solo para los primeros 2 usuarios
            historia_ejemplo = f"""
            Historia Clínica - {usuario[1]}
            Fecha: 2024-01-15
            
            Motivo de consulta: Control rutinario
            Antecedentes: Sin antecedentes médicos relevantes
            Examen físico: Normal
            Diagnóstico: Paciente en buen estado de salud
            Plan: Control anual
            """
            
            try:
                c.execute('INSERT INTO historias (usuario_id, contenido, archivo) VALUES (?, ?, ?)', 
                         (usuario[0], historia_ejemplo, 'ejemplo.pdf'))
                print(f"Historia agregada para: {usuario[1]}")
            except Exception as e:
                print(f"Error agregando historia para {usuario[1]}: {e}")
        
        conn.commit()
        conn.close()
        print("\n✅ Datos de ejemplo agregados exitosamente!")
        
    except Exception as e:
        print(f"❌ Error poblando datos: {e}")

if __name__ == '__main__':
    populate_sample_data()