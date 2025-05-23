import gurobipy as grb

from letturaKummer import IstanzaK
from letturaToy import IstanzaToy

from pydantic import BaseModel
import time
from typing import Tuple, Optional
import os

#leggere il file -> in input mettere il nome del file senza estensione
#data_set Mankowska -> letturaFile("istanza")
#file toy -> letturaToy("toy")

def ottimizza_file(filename:str) -> grb.Model:
    #---------------------DATASET MANKOWSKA----------------------------
    istanza=IstanzaK()
    istanza.letturaKummer(filename)

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
    # print(istanza.avs)
    # print(istanza.ris)
    for i in istanza.pazienti:
        for j in istanza.pazienti:
            for k in istanza.caregivers:
                for s in istanza.servizi:
                    if istanza.avs[k][s]==0:
                        model.addConstr(x[i,j,k,s] ==0)
    #i che non richiede s
    for i in istanza.pazienti:
        for j in istanza.pazienti+["0"]:
            for k in istanza.caregivers:
                for s in istanza.servizi:
                    if istanza.ris[j][s]==0:
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
        for k in istanza.caregivers:
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
            model.addConstr(grb.quicksum(istanza.avs[k][s]*x[j,i,k,s] for k in istanza.caregivers  for j in istanza.pazienti+["0"]) ==
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
                            if istanza.avs[k][s1]==1 and istanza.avs[k][s2]==1 and istanza.ris[i][s1]==1 and istanza.ris[j][s2]==1:
                                    model.addConstr(t[i,k,s1]+istanza.durataVisita[i]+istanza.distanzeDict[i][j]<=
                                            t[j,k,s2]+M*(1-x[i,j,k,s2]))
                                    # print(t[i,k,s1]+istanza.durataVisita[i]+istanza.distanzeDict[i][j]<=
                                    #         t[j,k,s2]+M*(1-x[i,j,k,s2]))

    #per il primo paziente
    for j in istanza.pazienti:
        for s1 in istanza.servizi:
                for k in istanza.caregivers:
                        model.addConstr(istanza.distanzeDaZero[j]<=t[j,k,s1]+(M*(1-x["0",j,k,s1])))

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
                        grb.quicksum(istanza.distanzeDict[i]["0"] * x[i, "0", k,s]
                                        for i in istanza.pazienti
                                        for k in istanza.caregivers
                                        for s in istanza.servizi)
                        )),

                    grb.GRB.MINIMIZE)

    model.update()
    # fa un file dove scrive tutte le variabili e i vincoli del problema
    model.write("modelloMank.lp")
    model.setParam('TimeLimit', 180)
    model.optimize()
    return model

class OutputModello(BaseModel):
    model_file: str
    optimal: bool
    processing_time:float
    upper_bound: Optional[float]
    lower_bound: Optional[float]


def crea_output(file_originale: str, model: grb.Model) -> None:
    # ---------------------------------STAMPA ------------------------------------
    # Verifica se è stata trovata una soluzione (ottima o meno)
    if model.status == grb.GRB.OPTIMAL or model.status == grb.GRB.TIME_LIMIT:
        print("\n--- Soluzione Trovata (potenzialmente sub-ottima) ---")

        # Se disponibile, stampa i bound
        if model.SolCount > 0:
            print(f"\nUpper Bound (valore funzione obiettivo trovato): {model.ObjVal:.3f}")
        if model.status == grb.GRB.TIME_LIMIT:
            print(f"Lower Bound (best bound): {model.ObjBound:.3f}")
        print(f"Tempo: {model.Runtime:.2f} secondi")

    output = OutputModello(model_file=file_originale,
                           optimal=model.status == grb.GRB.OPTIMAL,
                           processing_time=model.Runtime,
                           upper_bound=model.ObjVal if model.SolCount > 0 else None,
                           lower_bound=model.ObjBound)

    with open(os.path.join("risultati", "resultKummerM2_25.json"), "a", encoding="utf-8", newline="") as f:
        f.write(output.model_dump_json())



if __name__ == "__main__":
    for file in os.listdir("modelliKummer"):  # apre la cartella modelli
        modello_completato = ottimizza_file(os.path.join("modelliKummer", file))  # lanci il main
        crea_output(file, modello_completato)  # crea output