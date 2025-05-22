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
# print(istanza.mappa_pazienti_visitabili)
for k in istanza.caregivers:
    for i in istanza.pazienti+["0"]:
        for j in istanza.pazienti+["0"]:
            for s in istanza.servizi:
                 # if istanza.avs[k][s]*istanza.ris[j][s]==1 and i!=j:
                 #    if i in istanza.mappa_pazienti_visitabili[k] and j in istanza.mappa_pazienti_visitabili[k]:
                        x[i,j,k,s] = model.addVar(vtype=grb.GRB.BINARY, name=f'x({i},{j},{k},{s})')
                        # print(f'x({i},{j},{k},{s})')
                 #    else:
                 #        x[i, j, k, s] = model.addVar(vtype=grb.GRB.BINARY, name=f'x({i},{j},{k},{s})')
                 #        #model.addConstr(x[i, j, k, s] == 0)
                 # else:
                 #    x[i,j,k,s] = model.addVar(vtype=grb.GRB.BINARY, name=f'x({i},{j},{k},{s})')
                 #    #model.addConstr(x[i,j,k,s]==0)
#ci sono tutti devo mette a 0 tutte quelle dove k non può erogare s
#e tutte quelle dove j non richiede s


#creazione variabili t[i][k][s]
# tempo di inizio visita al paziente i-esimo del caregiver k per il servizio s
#li faccio senza lo 0 poi vedo
t={}
for i in istanza.pazienti:
        for k in istanza.caregivers:
            for s in istanza.servizi:
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
#k che non sa fare s
for i in istanza.pazienti:
    for j in istanza.pazienti:
        for k in istanza.caregivers:
            for s in istanza.servizi:
                if istanza.avs[k][s]==0:
                    model.addConstr(x[i,j,k,s] ==0)
#i che non richiede s
for i in istanza.pazienti:
    for j in istanza.pazienti:
        for k in istanza.caregivers:
            for s in istanza.servizi:
                if istanza.ris[i][s]==0:
                    model.addConstr(x[i,j,k,s]==0)
#le coppie i e j uguali
# # #SE METTO QUESTO NON TROVA SOLUZIONI
for i in istanza.pazienti:
    for j in istanza.pazienti:
        for k in istanza.caregivers:
            for s in istanza.servizi:
                if i==j:
                    model.addConstr(x[i,j,k,s]==0)

#vincolo 4 - per catturare il massimo ritardo e rendere lineare min(max)z[i]
for i in istanza.pazienti:
    for s in istanza.servizi:
        model.addConstr(Tmax>=z[i,s])

#vincolo 5 - tutti i k devono partire dal central office e tornare
for k in istanza.caregivers:
    model.addConstr(grb.quicksum(x["0",i,k,s] for i in istanza.pazienti+["0"] for s in istanza.servizi) == 1)

for k in istanza.caregivers:
    model.addConstr(grb.quicksum(x[i,"0",k,s] for i in istanza.pazienti+["0"] for s in istanza.servizi) == 1)

#vincolo 6 - conservazione del flusso
for i in istanza.pazienti:
    for k in istanza.patient_caregiver_map[i]:
        model.addConstr((grb.quicksum(x[j,i,k,s] for j in istanza.pazienti+["0"] for s in istanza.servizi)) ==
                        (grb.quicksum(x[i,j,k,s] for j in istanza.pazienti+["0"] for s in istanza.servizi )) )

#devo mettere bene a posto i servizi richiesti dai pazienti
#perchè di là ci sono quelli richiesti dai doppi e non li trova

#vincolo 7 - ogni servizio richiesto eseguito da un solo operatore
#ci sono variabili ridondanti perchè j non può essere tutti ma solo quelli che può visitare k
#però in teoria sono a 0 quelle variabili
# print (istanza.paziente_servizi['p10'])
for i in istanza.pazienti:
    for s in istanza.servizi:
        model.addConstr(grb.quicksum(istanza.avs[k][s]*x[j,i,k,s] for k in istanza.caregivers  for j in istanza.pazienti + ["0"]) ==
        istanza.ris[i][s])


#vincolo 8 - inizio tempi servizi consecutivi
#non so se vada bene per ogni s1 e s2
#controlla che le durate visiste siano tutte uguali
M = sum(istanza.durataVisita.values()) + sum(sum(subdict.values()) for subdict in istanza.distanzeDict.values())
#è senza i =0 ovvero senza il primo paziente 0->j

# QUESTI POSSO RIDURLI
for i in istanza.pazienti:
    for j in istanza.pazienti:
        for s1 in istanza.servizi:
            for s2 in istanza.servizi:
                for k in istanza.caregivers:
                    # if i!=j:
                        if istanza.avs[k][s1]==1 and istanza.avs[k][s2]==1 and istanza.ris[i][s1]==1 and istanza.ris[i][s2]==1:
                                model.addConstr(t[i,k,s1]+istanza.durataVisita[i]+istanza.distanzeDict[i][j]<=
                                        t[j,k,s2]+M*(1-x[i,j,k,s2]))
                                # print(t[i,k,s1]+istanza.durataVisita[i]+istanza.distanzeDict[i][j]<=
                                #         t[j,k,s2]+M*(1-x[i,j,k,s2]))

#per il primo paziente
for j in istanza.pazienti:
    for s1 in istanza.servizi:
        for s2 in istanza.servizi:
            for k in istanza.caregivers:
                    model.addConstr(0+0+istanza.distanzeDaZero[j]<=t[j,k,s1]+M*(1-x["0",j,k,s1]))

# print(istanza.distanzeDaZero['p1']<=t['p1','c3','s4']+M*(1-x["0",'p1','c3','s4']))

#vincolo 9
for i in istanza.pazienti:
    for s in istanza.servizi:
        for k in istanza.caregivers:
            model.addConstr(t[i,k,s]>=istanza.e[i])

#vincolo 10
for i in istanza.pazienti:
    for s in istanza.servizi:
        for k in istanza.caregivers:
                model.addConstr(t[i,k,s]<=istanza.l[i]+z[i,s])


#vincolo 11
print(istanza.pazientiDueServizi)
# for i in istanza.pazientiDueServizi:
#     for k1 in istanza.patient_caregiver_map[i]:
#         for k2 in istanza.patient_caregiver_map[i]:
#             if k1!=k2:
#                 s1=istanza.paziente_servizi[i][0]
#                 s2=istanza.paziente_servizi[i][1]
#                 if s1 in istanza.caregiver_servizi[k1] and s2 in istanza.caregiver_servizi[k2]:
#                     model.addConstr(t[i,k2,s2]-t[i,k1,s1]>=istanza.dictMin[i]
#                                     -(M*(2-(grb.quicksum(x[j,i,k1,s1] for j in istanza.pazienti + ["0"]))-
#                                          (grb.quicksum(x[j,i,k2,s2] for j in istanza.pazienti + ["0"])))))
#                     print(t[i,k2,s2]-t[i,k1,s1]>=istanza.dictMin[i]
#                                     -(M*(2-(grb.quicksum(x[j,i,k1,s1] for j in istanza.pazienti + ["0"]))-
#                                          (grb.quicksum(x[j,i,k2,s2] for j in istanza.pazienti + ["0"])))))

#vincolo 12
# for i in istanza.pazientiDueServizi:
#     for k1 in istanza.patient_caregiver_map[i]:
#         for k2 in istanza.patient_caregiver_map[i]:
#             if k1!=k2:
#                 s1=istanza.paziente_servizi[i][0]
#                 s2=istanza.paziente_servizi[i][1]
#                 if s1 in istanza.caregiver_servizi[k1] and s2 in istanza.caregiver_servizi[k2]:
#                     model.addConstr(t[i, k2, s2] - t[i, k1, s1] <= istanza.dictMax[i]
#                                 - M * (2 - grb.quicksum(x[j, i, k1, s1] for j in istanza.pazienti + ["0"]) -
#                                                         grb.quicksum(x[j, i, k2, s2] for j in istanza.pazienti + ["0"])))

#vincolo 11 riscritto
for i in istanza.pazientiDueServizi:
    for k1 in istanza.caregivers:
        for k2 in istanza.caregivers:
            s1 = istanza.paziente_servizi[i][0]
            s2 = istanza.paziente_servizi[i][1]
            model.addConstr(t[i, k2, s2] - t[i, k1, s1] >= istanza.dictMin[i]
                            - (M * (2 - (grb.quicksum(x[j, i, k1, s1] for j in istanza.pazienti + ["0"])) -
                                    (grb.quicksum(x[j, i, k2, s2] for j in istanza.pazienti + ["0"])))))
            # print(t[i, k2, s2] - t[i, k1, s1] >= istanza.dictMin[i]
            #                 - (M * (2 - (grb.quicksum(x[j, i, k1, s1] for j in istanza.pazienti + ["0"])) -
            #                         (grb.quicksum(x[j, i, k2, s2] for j in istanza.pazienti + ["0"])))))

#vincolo 12 riscritto
for i in istanza.pazientiDueServizi:
    for k1 in istanza.caregivers:
        for k2 in istanza.caregivers:
            s1 = istanza.paziente_servizi[i][0]
            s2 = istanza.paziente_servizi[i][1]
            model.addConstr(t[i, k2, s2] - t[i, k1, s1] <= istanza.dictMax[i]
                            + (M * (2 - (grb.quicksum(x[j, i, k1, s1] for j in istanza.pazienti + ["0"])) -
                                    (grb.quicksum(x[j, i, k2, s2] for j in istanza.pazienti + ["0"])))))
            # print(t[i, k2, s2] - t[i, k1, s1] <= istanza.dictMax[i]
            #                 + (M * (2 - (grb.quicksum(x[j, i, k1, s1] for j in istanza.pazienti + ["0"])) -
            #                         (grb.quicksum(x[j, i, k2, s2] for j in istanza.pazienti + ["0"])))))
#--------------------------------------FUNZIONE OBIETTIVO----------------------------------------------------------------
a=1/3 #peso della distanza percorsa
b=1/3 #peso per la sommatoria dei ritardi z[i]
c=1/3 #peso per il massimo ritardo D
#i pesi ai 3 addendi della f. obbiettivo sono settati dal paper


model.setObjective((c*Tmax+
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
                    )),

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


# Verifica che sia stata trovata una soluzione ottima
    if model.status == grb.GRB.OPTIMAL:
        print("\n--- Soluzione Ottima ---")


        # Stampa variabili x[i,j,k] == 1
        print("\n-> Variabili x[i,j,k] attive:")
        for (i, j, k,s), var in x.items():
                if var.X > 0.5:  # è binaria quindi basta > 0.5
                     print(f"x({i},{j},{k},{s}) = {int(var.X)}")


        # # Stampa percorsi ordinati per ogni caregiver
        # print("\n-> Percorsi per caregiver:")
        # for k in istanza.caregivers:
        #     percorso = []
        #     corrente = "0"  # partenza dal magazzino
        #     visitati = set()
        #
        #     while True:
        #         trovato_prossimo = False
        #         for j in istanza.pazientiVisitabili[istanza.caregivers.index(k)] + ["0"]:
        #             if (corrente, j, k) in x and x[corrente, j, k].X > 0.5:
        #                 percorso.append((corrente))
        #                 if j == "0":  # ritorno al magazzino
        #                     trovato_prossimo = False
        #                     break
        #                 corrente = j
        #                 if corrente in visitati:
        #                     break  # evitiamo cicli infiniti
        #                 visitati.add(corrente)
        #                 trovato_prossimo = True
        #                 break
        #         if not trovato_prossimo:
        #             break
        #
        #     if percorso:
        #         percorso_str=""
        #         for i in percorso:
        #             percorso_str += f'{i} -> '
        #         percorso_str += "0"
        #         print(f"Caregiver {k}: {percorso_str}")

        # Stampa variabili t[i,k,s]
        print("\n-> Variabili t[i,k,s] (tempi di inizio servizio):")
        for (i, k, s), var in t.items():
            if var.X > 1e-6:  # evita di stampare zeri numerici
                print(f"t({i},{k},{s}) = {var.X:.2f}")

        # Stampa variabili z[i,s]
        print("\n-> Variabili z[i,s] (ritardi):")
        for (i, s), var in z.items():
            if var.X > 1e-6:
                print(f"z({i},{s}) = {var.X:.2f}")

        # Stampa valore di Tmax
        print(f"\n-> Tmax (massimo ritardo): {Tmax.X:.2f}")


    #     # Calcolo e stampa della distanza totale percorsa
    #     distanza_totale = 0
    #     for (i, j, k), var in x.items():
    #         if var.X > 0.5:
    #             if i == "0":
    #                 distanza = istanza.distanzeDaZero[j]
    #             elif j == "0":
    #                 distanza = istanza.distanzeDaZero[i]
    #             else:
    #                 distanza = istanza.distanzeDict[i][j]
    #             distanza_totale += distanza
    #     print(f"\nDistanza totale percorsa: {distanza_totale:.3f}")
    #     # Stampa massimo ritardo D
    #     print(f"Massimo ritardo Dmax = {D.X:.3f}")
    #     #Stampa somma dei ritardi
    #     print (f'Somma dei singoli ritardi: {somma_ritardi:.3f}')
    #     # Stampa valore della funzione obiettivo
    #     print(f"\nValore funzione obiettivo: {model.ObjVal:.3f}")
    #
    # else:
    #     print("Non è stata trovata una soluzione ottima.")