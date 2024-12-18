# -*- coding: utf-8 -*-
"""
Created on Sun May 12 17:10:16 2024

@author: user3
"""

# Importacion de librerias para la creacion de la aplicacion
from flask import Flask, request, session

# Importacion de librerias para la generacion de respuestas
import os
import sys
from langchain.chains import ConversationalRetrievalChain
from langchain.chat_models import ChatOpenAI
from langchain.document_loaders import TextLoader
from langchain.embeddings import OpenAIEmbeddings
from langchain.indexes import VectorstoreIndexCreator
from langchain.indexes.vectorstore import VectorStoreIndexWrapper
from langchain.vectorstores import Chroma

# Importacion de librerias para el intercambio de mensajes
from twilio.twiml.messaging_response import MessagingResponse

# Importacion de librerias para la escritura de datos en hojas de Excel
import gspread
from google.oauth2.service_account import Credentials

# Creacion de la app
app=Flask(__name__)
app.secret_key = os.urandom(24)  # Clave secreta para las sesiones

# Variables de las sesiones, para identificar en que etapa esta el usuario
USER_STATES = {}
  
# Llave y su respectiva inicializacion para utilizar el modelo de OpenAI
APIKEY = ""
os.environ["OPENAI_API_KEY"] = APIKEY # Con este comando damos acceso a la api a nuestras variables

# Define el alcance y las credenciales para las hojas de calculo
scope = ['https://spreadsheets.google.com/feeds',
         'https://www.googleapis.com/auth/drive']
credentials = Credentials.from_service_account_file('credenciales_googleapi.json', scopes=scope)

# Autenticacion e inicio de sesion en Google Drive
gc = gspread.authorize(credentials)

# Definicion de la ruta y metodo para la aplicacion, se puede decir que esta es la funcion principal
@app.route('/chatgpt',methods=['POST'])

# Definicion de la funcion para el intercambion de mensajes
def chatgpt():
    solicitud=request.values.get('Body', '').lower()
    print("Pregunta: ",solicitud)
    
    # Asigna los caminos a seguir dependiendo la intencion del usuario
    if session.get('state') =='compra':
        session['nombre'] = solicitud
        nombre=session['nombre']
        guardar_datosi("COMPRA")
        guardar_datosn(nombre)
        session['state'] = 'esperando_telefono'
        respuesta = "Gracias "+nombre+". Ahora, ¿cuál es tu número de teléfono?"
        
    elif session.get('state') =='reclamo':
         session['nombre'] = solicitud
         nombre=session['nombre']
         guardar_datosi("RECLAMO")
         guardar_datosn(nombre)
         session['state'] = 'esperando_telefono'
         respuesta = "Gracias "+nombre+". Ahora, ¿cuál es tu número de teléfono?"
         
    elif session.get('state') == 'esperando_telefono':
        session['telefono'] = solicitud
        telefono=session['telefono']
        guardar_datost(telefono)
        session['state'] = 'esperando_descripcion'
        respuesta = "Me podrías dar una breve explicación de lo que buscas, por favor"
        
    elif session.get('state') == 'esperando_descripcion':
        session['descripcion'] = solicitud
        descripcion=session['descripcion']
        guardar_datosd(descripcion)
        session['state'] = None
        respuesta = "Gracias por proporcionar tu información. Un representante se comunicará contigo para asistirte a la brevedad. ¿Hay algo más en lo que te pueda ayudar?"    
        
    else:
        # Sino detecta ninguna intencion, simplemente brinda respuestas a las preguntas
        respuesta = generar_respuesta(solicitud)
    
    print("Respuesta: ",respuesta)
    respuesta_bot=MessagingResponse()
    mensaje=respuesta_bot.message()
    mensaje.body(respuesta)
    return str(respuesta_bot)

# Funcion para guardar la intencion en una nueva fila
def guardar_datosi(info):
    spreadsheet_key = ''
    worksheet_name = 'registros_verduglasa'
    worksheet = gc.open_by_key(spreadsheet_key).worksheet(worksheet_name)
    columna_nombre = worksheet.col_values(1)  # Obtiene todos los valores de la primera columna (nombre)
    # Encuentra la próxima fila vacía en la columna intencion
    proxima_fila = len(columna_nombre) + 1
    # Inserta los valores en las columnas correspondientes
    worksheet.update_cell(proxima_fila, 1, info)
    
# Funcion para guardar el nombre
def guardar_datosn(info):
    spreadsheet_key = ''
    worksheet_name = 'registros_verduglasa'  
    worksheet = gc.open_by_key(spreadsheet_key).worksheet(worksheet_name)
    columna_nombre = worksheet.col_values(1)  # Obtiene todos los valores de la primera columna (nombre) y continua escribiendo en la siguiente columna
    proxima_fila = len(columna_nombre)
    # Inserta los valores en las columnas correspondientes
    worksheet.update_cell(proxima_fila, 2, info)

# Funcion para guardar el numero
def guardar_datost(info):
    spreadsheet_key = ''
    worksheet_name = 'registros_verduglasa'  
    worksheet = gc.open_by_key(spreadsheet_key).worksheet(worksheet_name)
    columna_nombre = worksheet.col_values(1)  # Obtiene todos los valores de la primera columna (nombre) y continua escribiendo en la siguiente columna
    proxima_fila = len(columna_nombre)
    # Inserta los valores en las columnas correspondientes
    worksheet.update_cell(proxima_fila, 3, info)
    
# Funcion para guardar la descripcion
def guardar_datosd(info):
    spreadsheet_key = ''  
    worksheet_name = 'registros_verduglasa'
    worksheet = gc.open_by_key(spreadsheet_key).worksheet(worksheet_name)
    columna_nombre = worksheet.col_values(1)   # Obtiene todos los valores de la primera columna (nombre) y continua escribiendo en la siguiente columna
    proxima_fila = len(columna_nombre)
    # Inserta los valores en las columnas correspondientes
    worksheet.update_cell(proxima_fila, 4, info)
 
# Funcion para que el modelo genere las respuestas
def generar_respuesta(solicitud):
    # Habilita la opcion de guardar en disco y reutilizar el modelo (para consultas repetidas sobre los mismos datos)
    PERSIST = False

    # Se configura la variable consulta a vacia
    consulta = None
    
    # Esta parte se encarga de buscar informacion en la base de datos cargada
    if PERSIST and os.path.exists("persist"):
      print("Reutilizando indice...\n")
      vectorstore = Chroma(persist_directory="persist", embedding_function=OpenAIEmbeddings())
      indice = VectorStoreIndexWrapper(vectorstore=vectorstore)
    else:
      lectura_archivo = TextLoader("data/verduglasa_informacion.txt")
      if PERSIST:
        indice = VectorstoreIndexCreator(vectorstore_kwargs={"persist_directory":"persist"}).from_loaders([lectura_archivo])
      else:
        indice = VectorstoreIndexCreator().from_loaders([lectura_archivo])

    # Creacion de una cadena de recuperacion para generar la respuesta en base a la consulta, tambien se define que tan "creativas" seran las respuestas
    cadena = ConversationalRetrievalChain.from_llm(
      llm=ChatOpenAI(model="gpt-3.5-turbo", temperature=0.3),
      retriever=indice.vectorstore.as_retriever(search_kwargs={"k": 1}),
    )

    # Creacion de lista para almacenar las conversaciones
    historial_conversacion = []

    # Bucle principal que permite al usuario realizar consultas y obtener respuestas del chatbot.
    while True:
      if not consulta:
        consulta = solicitud
        
      # Asignamos palabras clave para finalizar el programa
      if consulta in ['bye',
                      'adios']:
        sys.exit()
      
      if consulta in ['quiero hacer una compra',
                      'quiero comprar',
                      'si quiero comprar',
                      'me interesa']:
          session['state']='compra'
          return "¡Qué gran decisión! Entiendo que estas interesado en hacer una compra. Para ello te pediré unos datos para que un representante se comunique contigo a la brevedad. ¿Me podrías brindar tu nombre por favor?"
      
      if consulta in ['quiero hacer un reclamo',
                      'tengo una queja',
                      'estoy insatisfecho']:
          session['state']='reclamo'
          return "Lamentamos mucho que tengas este inconveniente. Por favor brindame tus datos para que lo antes posible un representante se comunique contigo y resolvamos tu problema. ¿Cuál es tu nombre?"
      
      # La cadena de conversacion responde a la consulta
      resultado = cadena({"question": consulta, "chat_history": historial_conversacion})

      # La consulta y la respuesta se agregan al historial de conversaciones.
      historial_conversacion.append((consulta, resultado['answer']))
      
      # Se restablece la consulta para permitir al usuario hacer otra.
      consulta = None  
      
      return resultado['answer']

# Comando para ejecutar la aplicacion
if __name__=='__main__':
    app.run(host='0.0.0.0',debug=False,port=5000)