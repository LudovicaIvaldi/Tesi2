import gurobipy as grb
import os
from letturaMankowska import  Istanza
from letturaToy import IstanzaToy
from pydantic import BaseModel
import time
from typing import Tuple, Optional

#leggere il file -> in input mettere il nome del file senza estensione
#data_set Mankowska -> letturaFile("istanza")
#file toy -> letturaToy("toy")

def ottimizza_file(filename:str) -> Tuple[grb.Model,float]:

    #---------------------DATASET MANKOWSKA----------------------------
    istanza=Istanza()
    istanza.letturaFile(filename)

    #---------------------ISTANZA TOY------------------------------------
    # istanza = IstanzaToy()
    # istanza.letturaToy("toy")

    #--------------------------STAMPA PARAMENTRI ISTANZA -> set su cui cicla il modello HHC-----------------------------
    # print(istanza.pazienti)
    # print(istanza.caregivers)
    # print(istanza.pazientiDueServizi)
    # print(istanza.pazientiPrimi)
    # print(istanza.e)
    # print(istanza.l)
    # print(istanza.pazientiVisitabili)
    # print(istanza.dmin)
    # print(istanza.dmax)
    # print(istanza.durataVisita)
    # print(istanza.distanzeDict)
    # print(istanza.caregiversPossibili)
    # print(istanza.distanzeDaZero)

    #--------------------------Creazione del modello Gurobi---------------------------
    model = grb.Model('HHC')

    #--------------------------VARIABILI---------------------------------------

    #creazione variabili x[i][j][k] se il paziente i è visitato esattamente prima di j dal cargiver k
    #valgono 1; anche se k non visita i la variabile x[i][i][k] vale 1
    #le variabili sono create solo per i pazienti i e j che sono visitabili da k
    x = {}  # dizionario per tutte le variabili binarie
    for k in istanza.caregivers:
        for i in istanza.pazientiVisitabili[istanza.caregivers.index(k)]:
            for j in istanza.pazientiVisitabili[istanza.caregivers.index(k)]:
                x[i, j, k] = model.addVar(vtype=grb.GRB.BINARY, name=f'x({i},{j},{k})')

    #print(x)

    #creazione variabili t[i]
    # tempo di inizio visita al paziente i-esimo (continue, poi messe maggiori di e[i] con il vincolo)
    t={}
    for i in istanza.pazientiPrimi:
        t[i]=model.addVar(vtype=grb.GRB.CONTINUOUS, name=f't({i})',lb=0.0)

    #print(t)

    #creazione variabili z[i] ritardo fra l[i] (tempo massimo a cui puoi iniziare la prestazione) e t[i]
    # il modello me lo fa mettere su P' (i dati li ho solo su P), ma la supposizione è che la finestra
    #temporale e-l valga per entrambi i servizi allo stesso paziente (confermato dalla soluzione toy)
    z={}
    for i in istanza.pazientiPrimi:
        z[i]=model.addVar(vtype=grb.GRB.CONTINUOUS, name=f'z({i})',lb=0.0)

    #print(z)

    #variabile continua D per catturare il massimo ritardo e rendere lineare il vincolo di min(max) z[i]
    D=model.addVar(vtype=grb.GRB.CONTINUOUS, name=f'D',lb=0.0)

    #print(D)

    #-------------------------------------VINCOLI-------------------------------------------

    #vincolo 1 è la f. obb. al fondo

    #vincolo 2 - per catturare il massimo ritardo e rendere lineare min(max)z[i]
    for i in istanza.pazientiPrimi:
        model.addConstr(D>=z[i])


    #vincolo 3 -> imporre a 1 le variabili x[i][i][k] quando NON si visita
    # per tutti i k, per tutti i pazienti visitabili da k (secondo me in P'k, secondo il modello in Pk),
    # sommando su tutti le variabili che dicono se un paziente j è visitato esattamente prima di i deve fare 1
    #quindi o sono arrivato al paziente i da un generico j (fra j c'è anche lo 0 magazzino)
    #oppure vale 1 x[i][i][k] che significa che k NON visita i (non ho un flusso che va da un j a i)
    for k in istanza.caregivers:
        for i in istanza.pazientiVisitabili[istanza.caregivers.index(k)]:
            model.addConstr(grb.quicksum(x[j,i,k] for j in istanza.pazientiVisitabili[istanza.caregivers.index(k)]) == 1)

    #rimane la possibilità che un k visiti paziente e paziente' -> va tolta con il vincolo 9


    #vincolo 4 - continuità del flusso
    #se k arriva in i da un generico j allora ripartirà da i e andrà in un altro generico j
    #devo togliere i e j uguali perchè sono a 1 se k NON lo visita
    #!!!Nel .pl i vincoli sono con addendi mischiati!!!1
    for k in istanza.caregivers:
        for i in istanza.pazientiVisitabili[istanza.caregivers.index(k)]:
            model.addConstr(grb.quicksum(x[j,i,k] for j in istanza.pazientiVisitabili[istanza.caregivers.index(k)] if j!=i) ==
                            grb.quicksum(x[i,j,k] for j in istanza.pazientiVisitabili[istanza.caregivers.index(k)] if j!=i))


    #vincolo 5 - costruzione dei ritardi z[i] (li metti >= tanto poi minimizzi quindi verranno =)
    #li ho costruiti per tutti i pazienti anche i doppi, tendo come l del doppio lo stesso l del paziente
    #significa che nella finestra di tempo e-l devi erogare sia il primo che il secondo servizio
    for i in istanza.pazientiPrimi:
        model.addConstr(z[i]>=t[i]-istanza.l[i])


    #vincolo 6 - se un k serve in sequenza i e j (quindi x[i][j][k]=1) e si attiva il big-M
    # allora il t[j] deve essere almeno pari al t[i] + durataServizio[i] + distanza[i][j]
    #se non si attiva il vincolo di big-M allora t[j] non deve avere "blocchi", per cui posso mettere che sia >=0 o numero negativo
    #per fare questo fisso M abbastanza alta -> se esagero viene t[j]>= numero tanto negativo che va bene
    #basterebbe mettere che M sia pari a t[i] + durataServizio[i] + distanza[i][j] ma per non calcolare sempre M e
    # lasciarla costante per tutti i vincoli mi faccio una volta i max su tutti
    M = sum(istanza.durataVisita.values()) + sum(sum(subdict.values()) for subdict in istanza.distanzeDict.values())
    #è come se facesse tutte le visite 1 solo k, sommando così la distanze ti viene M grande ma va bene lo stesso

    #Problema: le distanze e le durate delle visite le ho solo per i pazienti e non per il nodo 0 (magazzino)
    #salto il primo elemento degli insiemi P'k, ma il t di inizio del primo paziente deve comunque avere il vincolo di iniziare
    #dopo il trasferimento dal magazzino al paziente -> aggiungo vincolo dopo
    for k in istanza.caregivers:
        for i in istanza.pazientiVisitabili[istanza.caregivers.index(k)][1:]:
            for j in istanza.pazientiVisitabili[istanza.caregivers.index(k)][1:]:
                if i != j:
                    # print(istanza.durataVisita[i])
                    # print(istanza.distanzeDict[i][j])
                    # print(M)
                    # print(x[i,j,k])
                    model.addConstr(t[j]>=t[i]+istanza.durataVisita[i]+istanza.distanzeDict[i][j]-M+M*x[i,j,k])
                    #nel .pl del modello fa la somma dei numeri quindi vedi 1 solo addendo


    #-----------------------------VINCOLO AGGIUNTIVO------------------------------
    #Il vincolo di prima vale per tutti i pazienti p
    #introduco il vincolo che i pazienti visitati per primi, quindi quelli che hanno x(0jk) devono avere un tempo di inizio j
    #almeno pari alla distanza fra il magazzino e il paziente (non c'è la durata visita di 0)
    #ovviamento solo se il p j-esimo è visitato dopo lo 0, quindi è di big-M anche questo vincolo
    for k in istanza.caregivers:
            for j in istanza.pazientiVisitabili[istanza.caregivers.index(k)][1:]: #togli il primo perchè crea la variabile x(00k)
                    model.addConstr(t[j]>=istanza.distanzeDaZero[j]-M+M*x["0",j,k])

    #-----------------------------------------------------------------------

    #vincolo 7- per ogni paziente con due servizi, impongo che il secondo servizio (ovvero t[i] del paziente doppio p') sia
    #compreso fra il ritardo minimo e massimo a cui possono essere erogati i servizi
    #per i servizi in contemporanea metto 0 sia a dmin che a dmax (messo nella lettura file)-> t[p] e t[p'] saranno uguali
    for j in istanza.pazientiDoppi:
        indice=istanza.pazientiDoppi.index(j)
        model.addConstr(istanza.dmin[indice]<=t[j]-t[istanza.pazientiDueServizi[indice]])
        model.addConstr(t[j]-t[istanza.pazientiDueServizi[indice]]<=istanza.dmax[indice])


    #vincolo 8 - un caregiver per servire dei pazienti deve essere partito dalla centrale (nodo 0 magazzino)
    #se x["0","0",k]=1, quindi il k NON parte, allora nessuna variabile a lui associata può valere 1
    for k in istanza.caregivers:
        for i in istanza.pazientiVisitabili[istanza.caregivers.index(k)]:
            for j in istanza.pazientiVisitabili[istanza.caregivers.index(k)]:
                if i!=j:
                    model.addConstr(x[i,j,k]<=1-x["0","0",k])
                    model.update()

    #vincolo 9 - i pazienti che ricevono due servizi devono essere serviti da 2 k diversi (imposto dal problema)
    #per ogni k e per ogni paziente i che richiede due servizi
    #se k può servirlo
    #cerchi il doppio del paziente i -> j
    #se k può servire ance j allora devi imporre che o serve i o serve j
    #sommi su tutti i pazienti l servibili prima di i + tutti gli l servibili vero j e lo metti <=1
    #o serve i (arriva da un l e "cade" in i) o serve j (arriva da un l e "cade" in j)
    for k in istanza.caregivers:
            for i in istanza.pazientiDueServizi:
                if i in istanza.pazientiVisitabili[istanza.caregivers.index(k)]:
                    indice = istanza.pazientiDueServizi.index(i)
                    j=istanza.pazientiDoppi[indice]
                    if j in istanza.pazientiVisitabili[istanza.caregivers.index(k)]:
                        model.addConstr((grb.quicksum(x[l,i,k] for l in istanza.pazientiVisitabili[istanza.caregivers.index(k)] if l!=i)) +
                                    (grb.quicksum(x[l,j,k] for l in istanza.pazientiVisitabili[istanza.caregivers.index(k)] if l!=j))<=1)

    #vincolo 10 - le x sono variabili binarie (messo nella definizione delle variabili)

    #vincolo 11 - i tempi di inizio visita devono essere maggiori o uguali all'inizio della finestra
    #temporale di esecuzione della visita e-l
    for i in istanza.pazientiPrimi:
        model.addConstr(t[i]>=istanza.e[i])

    model.update()

    #vincolo 12 e vincolo 13 sono nella def delle variabili

    #-------------------------------VINCOLO AGGIUNTIVO-------------------------------------
    #vincolo tutti i pazienti devono essere visitati -> non c'è nel modello ma se non lo metto
    #giustamente mi dice che l'ottimo è non far partire nessun caregiver
    #Per tutti i pazienti, sommando su tutti i k che possono servire quel paziente e su tutti i pazienti i (compreso lo 0) da cui
    #k potrebbe arrivare, deve fare 1 -> ovvero j deve essere servito da uno e un solo k, dopo uno e un solo i (anche magazzino)
    #funziona per i servizi doppi perchè in realtà sono un altro j -> p e p'
    for j in istanza.pazientiPrimi:
        model.addConstr(grb.quicksum(x[i,j,k]
                                    for i in istanza.pazientiPrimi+["0"]
                                    for k in istanza.caregivers
                                    if i!=j
                                    if i in istanza.pazientiVisitabili[istanza.caregivers.index(k)]
                                    if j in istanza.pazientiVisitabili[istanza.caregivers.index(k)]
                                    )==1 )



    #------------------------------------FUNZIONE OBBIETTIVO--------------------------------
    a=1/3 #peso della distanza percorsa
    b=1/3 #peso per la sommatoria dei ritardi z[i]
    c=1/3 #peso per il massimo ritardo D
    #i pesi ai 3 addendi della f. obbiettivo sono settati dal paper


    model.setObjective(c*D+
                    b*(grb.quicksum(z[i] for i in istanza.pazientiPrimi))+
                        a*(grb.quicksum(istanza.distanzeDaZero[j] * x["0", j, k]
                                        for j in istanza.pazientiPrimi
                                        for k in istanza.caregivers
                                        if j in istanza.pazientiVisitabili[istanza.caregivers.index(k)])+
                            grb.quicksum(istanza.distanzeDict[i][j] * x[i, j, k]
                                        for i in istanza.pazientiPrimi
                                        for j in istanza.pazientiPrimi
                                        if i != j
                                        for k in istanza.caregivers
                                        if k in istanza.caregiversPossibili[i] and k in istanza.caregiversPossibili[j])+
                        grb.quicksum(istanza.distanzeDaZero[j] * x[j, "0", k]
                                        for j in istanza.pazientiPrimi
                                        for k in istanza.caregivers
                                        if j in istanza.pazientiVisitabili[istanza.caregivers.index(k)])
                        ),

                    grb.GRB.MINIMIZE)
    model.update()

    # fa un file dove scrive tutte le variabili e i vincoli del problema
    # model.write("modello.lp")

    # Imposta il limite di tempo di 120 secondi (2 minuti)
    model.setParam('TimeLimit', 10)
    start_time = time.perf_counter()
    model.optimize()
    processing_time = time.perf_counter()-start_time
    return model,processing_time


class OutputModello(BaseModel):
    model_file: str
    optimal: bool
    processing_time:float
    upper_bound: Optional[float]
    lower_bound: Optional[float]


def crea_output(file_originale:str,model: grb.Model,processing_time:float) -> None:
    #---------------------------------STAMPA ------------------------------------
    # Verifica se è stata trovata una soluzione (ottima o meno)
    if model.status == grb.GRB.OPTIMAL or model.status == grb.GRB.TIME_LIMIT:
        print("\n--- Soluzione Trovata (potenzialmente sub-ottima) ---")

        # Se disponibile, stampa i bound
        if model.SolCount > 0:
            print(f"\nUpper Bound (valore funzione obiettivo trovato): {model.ObjVal:.3f}")
        if model.status == grb.GRB.TIME_LIMIT:
            print(f"Lower Bound (best bound): {model.ObjBound:.3f}")

    output = OutputModello(model_file=file_originale,
                           optimal=model.status == grb.GRB.OPTIMAL,
                           processing_time= processing_time,
                           upper_bound = model.ObjVal if model.SolCount > 0 else None,
                           lower_bound = model.ObjBound)
    
    with open(os.path.join("risultati","result.json"),"a",encoding="utf-8",newline="") as f:
        f.write(output.model_dump_json())
    # # Verifica che sia stata trovata una soluzione ottima
    # if model.status == grb.GRB.OPTIMAL:
    #     print("\n--- Soluzione Ottima ---")


    #     # Stampa variabili x[i,j,k] == 1
    #     print("\n-> Variabili x[i,j,k] attive:")
    #     for (i, j, k), var in x.items():
    #         if i!=j: #non stampo quelle a 1 con i=j perchè sono quando k NON va dai pazienti
    #             if var.X > 0.5:  # è binaria quindi basta > 0.5
    #                  print(f"x({i},{j},{k}) = {int(var.X)}")


    #     # Stampa percorsi ordinati per ogni caregiver
    #     print("\n-> Percorsi per caregiver:")
    #     for k in istanza.caregivers:
    #         percorso = []
    #         corrente = "0"  # partenza dal magazzino
    #         visitati = set()

    #         while True:
    #             trovato_prossimo = False
    #             for j in istanza.pazientiVisitabili[istanza.caregivers.index(k)] + ["0"]:
    #                 if (corrente, j, k) in x and x[corrente, j, k].X > 0.5:
    #                     percorso.append((corrente))
    #                     if j == "0":  # ritorno al magazzino
    #                         trovato_prossimo = False
    #                         break
    #                     corrente = j
    #                     if corrente in visitati:
    #                         break  # evitiamo cicli infiniti
    #                     visitati.add(corrente)
    #                     trovato_prossimo = True
    #                     break
    #             if not trovato_prossimo:
    #                 break

    #         if percorso:
    #             percorso_str=""
    #             for i in percorso:
    #                 percorso_str += f'{i} -> '
    #             percorso_str += "0"
    #             print(f"Caregiver {k}: {percorso_str}")

    #     # Stampa tempi di inizio visita
    #     print("\n-> Tempi di inizio visita t[i]:")
    #     for i, var in t.items():
    #         print(f"t({i}) = {var.X:.2f}")

    #     # Stampa ritardi z[i]
    #     print("\n-> Ritardi z[i]:")
    #     somma_ritardi=0
    #     for i, var in z.items():
    #         somma_ritardi += var.X
    #         print(f"z({i}) = {var.X:.2f}")


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

    # else:
    #     print("Non è stata trovata una soluzione ottima.")

if __name__ == "__main__":
    for file in os.listdir("modelli"): #apre la cartella modelli
        modello_completato,tempo_di_elaborazione_s = ottimizza_file(os.path.join("modelli",file)) #lanci il main
        crea_output(file,modello_completato,tempo_di_elaborazione_s) #crea output
