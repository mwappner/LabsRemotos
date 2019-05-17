#!/bin/bash

# Uso: barrido.sh [tiempo] [frec inicial] [frec final]
echo "Subo el volumen al 100..."
amixer set PCM -- 100%
echo "Listo"
echo "Empiezo a filmar durante tiempo $1"
raspivid -o video/filmacion.h264 -w 960 -h 516 -roi 0,0.5,1,1 -ex off -n -br 70 -co 50 -t $(($1*1000)) -v&
echo "Filmacion en segundo plano"
echo "Genero la señal"
echo "Reproduzco un barrido desde $2 a $3 durante $1 segundos..."
play -n synth $1 sine $2:$3
echo "Programa finallizado."
