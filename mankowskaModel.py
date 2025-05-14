import gurobipy as grb

from letturaMankowska import  Istanza
from letturaToy import IstanzaToy

#leggere il file -> in input mettere il nome del file senza estensione
#data_set Mankowska -> letturaFile("istanza")
#file toy -> letturaToy("toy")

#---------------------DATASET MANKOWSKA----------------------------
istanza=Istanza()
istanza.letturaFile("InstanzCPLEX_HCSRP_10_1")

#---------------------ISTANZA TOY------------------------------------
# istanza = IstanzaToy()
# istanza.letturaToy("toy")



#--------------------------Creazione del modello Gurobi---------------------------
model = grb.Model('HHC')

#--------------------------VARIABILI---------------------------------------

#creazione variabili x[i][j][k][s] se il paziente i è visitato esattamente prima di j dal cargiver k eseguendo il servizio s
x = {}  # dizionario per tutte le variabili binarie
for k in istanza.caregivers:
    for i in istanza.pazienti+["0"]:
        for j in istanza.pazienti+["0"]:
            for s in istanza.servizi:
                x[i, j, k,s] = model.addVar(vtype=grb.GRB.BINARY, name=f'x({i},{j},{k},{s})')

#ci sono tutti devo mette a 0 tutte quelle dove k non può erogare s
#e tutte quelle dove j non richiede s

#print(x)

#creazione variabili t[i][k][s]
# tempo di inizio visita al paziente i-esimo del caregiver k per il servizio s
#li faccio senza lo 0 poi vedo
t={}
for k in istanza.caregivers:
    for i in istanza.pazienti:
            for s in istanza.paziente_servizi[i]:
                #crei t solo per i servizi richiesti da ogni i
                t[i,k,s]=model.addVar(vtype=grb.GRB.CONTINUOUS, name=f't({i},{k},{s})',lb=0.0)

#print(t)

#creazione variabili z[i][s] ritardo fra l[i] (tempo massimo a cui puoi iniziare la prestazione) e t[i]
z={}
for i in istanza.pazienti:
    for s in istanza.paziente_servizi[i]:
        z[i,s]=model.addVar(vtype=grb.GRB.CONTINUOUS, name=f'z({i},{s})',lb=0.0)

#print(z)

#variabile continua Tmax per catturare il massimo ritardo e rendere lineare il vincolo di min(max) z[i]
Tmax=model.addVar(vtype=grb.GRB.CONTINUOUS, name=f'D',lb=0.0)

#print(D)



#-------------------------------------VINCOLI-------------------------------------------

#Mettere a 0 tutte le variabili che non devono esistere
#servizi non richiesti

for i in istanza.pazienti+["0"]:
    for j in istanza.pazienti+["0"]:
        for k in istanza.caregivers:
            for s in istanza.servizi:
                if s not in istanza.paziente_servizi[j]:
                    model.addConstr(x[i,j,k,s]==0)

#caregiver che non sanno eseguire
for i in istanza.pazienti+["0"]:
    for j in istanza.pazienti+["0"]:
        for k in istanza.caregivers:
            for s in istanza.servizi:
                if s not in istanza.caregiver_servizi[k]:
                    model.addConstr(x[i,j,k,s]==0)


#vincolo 4 - per catturare il massimo ritardo e rendere lineare min(max)z[i]
for i in istanza.pazienti:
    for s in istanza.paziente_servizi[i]:
        model.addConstr(Tmax>=z[i,s])

#vincolo 5 - tutti i k devono partire dal central office e tornare
for k in istanza.caregivers:
    model.addConstr(grb.quicksum(x[0, i, k,s] for i in istanza.pazienti+["0"] for s in istanza.servizi) == 1)
for k in istanza.caregivers:
    model.addConstr(grb.quicksum(x[i, 0, k,s] for i in istanza.pazienti+["0"] for s in istanza.servizi) == 1)

#vincolo 6 - conservazione del flusso
for i in istanza.pazienti:
    for k in istanza.caregivers:
        model.addConstr(grb.quicksum(x[j, i, k, s] for j in istanza.pazienti + ["0"] for s in istanza.servizi) ==
                        grb.quicksum(x[i, j, k, s] for j in istanza.pazienti + ["0"] for s in istanza.servizi))


#vincolo 7 - ogni servizio richiesto eseguito da un solo operatore
#non ho a e v ???????????




model.update()
# fa un file dove scrive tutte le variabili e i vincoli del problema
model.write("modello.lp")
