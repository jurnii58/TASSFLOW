import os
import sys
os.environ['SPARK_HOME'] = sys.prefix + '\\Lib\\site-packages\\pyspark'
from dotenv import load_dotenv
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count, desc

print(" Iniciando Motor Analítico Apache Spark para TaskFlow...")

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    print("Error: Variable de entorno MONGO_URI no encontrada.")
    exit(1)

spark = SparkSession.builder \
    .appName("TaskFlow_Analytics") \
    .config("spark.jars.packages", "org.mongodb.spark:mongo-spark-connector_2.12:10.4.0") \
    .getOrCreate()

spark.sparkContext.setLogLevel("ERROR")

print(" Conectado a MongoDB. Extrayendo 1,000,000 de tareas en memoria...")

df_tareas = spark.read.format("mongodb") \
    .option("connection.uri", MONGO_URI) \
    .option("database", "carga_mental_db") \
    .option("collection", "tareas") \
    .load()

# ANÁLISIS DE BIG DATA

print(" REPORTE DE CARGA DE TRABAJO (ESTADO)")
df_estado = df_tareas.groupBy("estado") \
    .agg(count("*").alias("total_tareas")) \
    .orderBy(desc("total_tareas"))
df_estado.show()

print(" TAREAS PENDIENTES POR EMPLEADO (CUELLOS DE BOTELLA)")
df_empleados = df_tareas.filter(col("estado") == "Pendiente") \
    .groupBy("usuarios") \
    .agg(count("*").alias("tareas_atrasadas")) \
    .orderBy(desc("tareas_atrasadas"))
df_empleados.show()

print(" URGENCIAS: TAREAS CRÍTICAS NO RESUELTAS (ALTA PRIORIDAD)")
df_criticas = df_tareas.filter((col("estado") == "Pendiente") & (col("prioridad") == "Alta")) \
    .groupBy("usuarios") \
    .agg(count("*").alias("tareas_criticas")) \
    .orderBy(desc("tareas_criticas"))
df_criticas.show()

spark.stop()