import gurobipy as grb

from letturaMankowska import  Istanza
from letturaToy import IstanzaToy

#leggere il file -> in input mettere il nome del file senza estensione
#data_set Mankowska -> letturaFile("istanza")
#file toy -> letturaToy("toy")

#---------------------DATASET MANKOWSKA----------------------------
istanza=Istanza()
istanza.letturaFile("InstanzCPLEX_HCSRP_10_1.json")

#---------------------ISTANZA TOY------------------------------------
# istanza = IstanzaToy()
# istanza.letturaToy("toy")


#--------------------------Creazione del modello Gurobi---------------------------
model = grb.Model('HHC')

#--------------------------VARIABILI---------------------------------------

#creazione variabili x[i][j][k][s] se il paziente i è visitato esattamente prima di j dal cargiver k eseguendo il servizio s
x = {}  # dizionario per tutte le variabili binarie
# print(istanza.ris)
for k in istanza.caregivers:
    for i in istanza.pazienti+["0"]:
        for j in istanza.pazienti+["0"]:
            for s in istanza.servizi:
                if istanza.avs[k][s]*istanza.ris[j][s]==1:
                    x[i,j,k,s] = model.addVar(vtype=grb.GRB.BINARY, name=f'x({i},{j},{k},{s})')
                    # print(f'x({i},{j},{k},{s})')
                else:
                    x[i, j, k, s]=0
#ci sono tutti devo mette a 0 tutte quelle dove k non può erogare s
#e tutte quelle dove j non richiede s


#creazione variabili t[i][k][s]
# tempo di inizio visita al paziente i-esimo del caregiver k per il servizio s
#li faccio senza lo 0 poi vedo
t={}
for k in istanza.caregivers:
    for i in istanza.pazienti:
            for s in istanza.servizi:
                #crei t solo per i servizi richiesti da ogni i
                t[i,k,s]=model.addVar(vtype=grb.GRB.CONTINUOUS, name=f't({i},{k},{s})',lb=0.0)



#creazione variabili z[i][s] ritardo fra l[i] (tempo massimo a cui puoi iniziare la prestazione) e t[i]
z={}
for i in istanza.pazienti:
    for s in istanza.servizi:
        z[i,s]=model.addVar(vtype=grb.GRB.CONTINUOUS, name=f'z({i},{s})',lb=0.0)

#print(z)

#variabile continua Tmax per catturare il massimo ritardo e rendere lineare il vincolo di min(max) z[i]
Tmax=model.addVar(vtype=grb.GRB.CONTINUOUS, name=f'Tmax',lb=0.0)

#print(D)

model.update()

#-------------------------------------VINCOLI-------------------------------------------

#Mettere a 0 tutte le variabili che non devono esistere
#servizi non richiesti

# for i in istanza.pazienti+["0"]:
#     for j in istanza.pazienti+["0"]:
#         for k in istanza.caregivers:
#             for s in istanza.servizi:
#                 if s not in istanza.paziente_servizi[j]:
#                     model.addConstr(x[i,j,k,s]==0)
#
# #caregiver che non sanno eseguire
# for i in istanza.pazienti+["0"]:
#     for j in istanza.pazienti+["0"]:
#         for k in istanza.caregivers:
#             for s in istanza.servizi:
#                 if s not in istanza.caregiver_servizi[k]:
#                     model.addConstr(x[i,j,k,s]==0)

# for i in istanza.pazienti+["0"]:
#     for j in istanza.pazienti:
#         for k in istanza.caregivers:
#             for s in istanza.servizi:
#                 if istanza.avs[k][s]*istanza.ris[j][s]==0 or i==j:
#                     model.addConstr(x[i,j,k,s] == 0)
#                 elif i=="p1":
#                     print(x[i,j,k,s])




#vincolo 4 - per catturare il massimo ritardo e rendere lineare min(max)z[i]
for i in istanza.pazienti:
    for s in istanza.paziente_servizi[i]:
        model.addConstr(Tmax>=z[i,s])

#vincolo 5 - tutti i k devono partire dal central office e tornare
for k in istanza.caregivers:
    model.addConstr(grb.quicksum(x["0",i,k,s] for i in istanza.pazienti+["0"] for s in istanza.servizi) == 1)

for k in istanza.caregivers:
    model.addConstr(grb.quicksum(x[i,"0",k,s] for i in istanza.pazientiVisitabili[istanza.caregivers.index(k)] if i[-1]!="'" for s in istanza.servizi) == 1)

#vincolo 6 - conservazione del flusso
print (istanza.caregiversPossibili)
for i in istanza.pazienti:
    for k in istanza.caregiversPossibili[i]:
        model.addConstr((grb.quicksum(x[j,i,k,s] for j in istanza.pazienti+["0"] for s in istanza.paziente_servizi[i])) ==
                        (grb.quicksum(x[i,j,k,s] for j in istanza.pazienti+["0"] for s in istanza.paziente_servizi[j])) )



#vincolo 7 - ogni servizio richiesto eseguito da un solo operatore
for i in istanza.pazienti:
    for s in istanza.paziente_servizi[i]:
        model.addConstr(grb.quicksum(istanza.avs[k][s]*x[j,i,k,s] for k in istanza.caregivers  for j in istanza.pazienti + ["0"]) ==
        istanza.ris[i][s])


#vincolo 8 - inizio tempi servizi consecutivi
#non so se vada bene per ogni s1 e s2
#controlla che le durate visiste siano tutte uguali
M = sum(istanza.durataVisita.values()) + sum(sum(subdict.values()) for subdict in istanza.distanzeDict.values())
#è senza i =0 ovvero senza il primo paziente 0->j
for i in istanza.pazienti:
    for j in istanza.pazienti:
        for s1 in istanza.paziente_servizi[i]:
            for s2 in istanza.paziente_servizi[j]:
                for k in istanza.caregivers:
                    if s1 in istanza.caregiver_servizi[k] and s2 in istanza.caregiver_servizi[k]:
                        if i!=j:
                            model.addConstr(t[i,k,s1]+istanza.durataVisita[i]+istanza.distanzeDict[i][j]<=
                                    t[j,k,s2]+M*(1-x[i,j,k,s2]))

#per il primo paziente
for j in istanza.pazienti:
    for s1 in istanza.paziente_servizi[j]:
            for k in istanza.caregivers:
                if s1 in istanza.caregiver_servizi[k]:
                    model.addConstr(0+0+istanza.distanzeDaZero[j]<=t[j,k,s1]+M*(1-x["0",j,k,s1]))

#vincolo 9
for i in istanza.pazienti:
    for s in istanza.paziente_servizi[i]:
        for k in istanza.caregivers:
            if s in istanza.caregiver_servizi[k]:
                model.addConstr(t[i,k,s]>=istanza.e[i])

#vincolo 10
for i in istanza.pazienti:
    for s in istanza.paziente_servizi[i]:
        for k in istanza.caregivers:
            if s in istanza.caregiver_servizi[k]:
                model.addConstr(t[i,k,s]<=istanza.l[i]+z[i,s])


#vincolo 11
for i in istanza.pazientiDueServizi:
    for k1 in istanza.caregivers:
        for k2 in istanza.caregivers:
            s1=istanza.paziente_servizi[i][0]
            s2=istanza.paziente_servizi[i][1]
            model.addConstr(t[i,k2,s2]-t[i,k1,s1]>=istanza.dictMin[i]
                            -M*(2-grb.quicksum(x[j,i,k1,s1] for j in istanza.pazienti + ["0"])-
                                grb.quicksum(x[j,i,k2,s2] for j in istanza.pazienti + ["0"])))


#vincolo 12
for i in istanza.pazientiDueServizi:
    for k1 in istanza.caregivers:
        for k2 in istanza.caregivers:
            s1 = istanza.paziente_servizi[i][0]
            s2 = istanza.paziente_servizi[i][1]
            model.addConstr(t[i, k2, s2] - t[i, k1, s1] <= istanza.dictMax[i]
                            - M * (2 - grb.quicksum(x[j, i, k1, s1] for j in istanza.pazienti + ["0"]) -
                                                    grb.quicksum(x[j, i, k2, s2] for j in istanza.pazienti + ["0"])))


#--------------------------------------FUNZIONE OBIETTIVO----------------------------------------------------------------
a=1/3 #peso della distanza percorsa
b=1/3 #peso per la sommatoria dei ritardi z[i]
c=1/3 #peso per il massimo ritardo D
#i pesi ai 3 addendi della f. obbiettivo sono settati dal paper


model.setObjective(c*Tmax+
                b*(grb.quicksum(z[i,s] for i in istanza.pazienti for s in istanza.servizi))+
                    a*(grb.quicksum(istanza.distanzeDaZero[j] * x["0", j, k,s]
                                    for j in istanza.pazienti
                                    for k in istanza.caregivers
                                    for s in istanza.servizi)+
                        grb.quicksum(istanza.distanzeDict[i][j] * x[i, j, k,s]
                                    for i in istanza.pazienti
                                    for j in istanza.pazienti
                                    for k in istanza.caregivers
                                   for s in istanza.servizi)+
                    grb.quicksum(istanza.distanzeDaZero[j] * x[j, "0", k,s]
                                    for j in istanza.pazienti
                                    for k in istanza.caregivers
                                    for s in istanza.servizi)
                    ),

                grb.GRB.MINIMIZE)

model.update()
# fa un file dove scrive tutte le variabili e i vincoli del problema
model.write("modelloMank.lp")

model.optimize()

if model.status == grb.GRB.OPTIMAL or model.status == grb.GRB.TIME_LIMIT:
    print("\n--- Soluzione Trovata (potenzialmente sub-ottima) ---")

    # Se disponibile, stampa i bound
    if model.SolCount > 0:
        print(f"\nUpper Bound (valore funzione obiettivo trovato): {model.ObjVal:.3f}")
    if model.status == grb.GRB.TIME_LIMIT:
        print(f"Lower Bound (best bound): {model.ObjBound:.3f}")
