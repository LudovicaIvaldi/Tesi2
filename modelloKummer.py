import gurobipy as grb

from letturaKummer import IstanzaK

#---------------------parte nuova nella F. Obb.

istanza=IstanzaK()
istanza.letturaKummer("HHCRSP_75_15_10_1.6_R_C")


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

# Creazione del modello Gurobi
model = grb.Model('HHC')

#--------------------------VARIABILI---------------------------------------
#-----------------uguali al modello classico---------------------------------

#creazione variabili x[i][j][k] se il paziente i è visitato esattamente prima di j da k
#valgono 1 anche se k non visita i per la variabile x[i][i][k]
x = {}  # dizionario per tutte le variabili binarie

for k in istanza.caregivers:
    for i in istanza.pazientiVisitabili[istanza.caregivers.index(k)]:
        for j in istanza.pazientiVisitabili[istanza.caregivers.index(k)]:
            x[i, j, k] = model.addVar(vtype=grb.GRB.BINARY, name=f'x({i},{j},{k})')
            model.update()
#print(x)

#creazione variabili t[i] tempo di inizio visita al paziente i-esimo (continue in teoria positive e maggiori di e[i]
# ma tanto c'è poi il vincolo)
#non so se ha senso avere lo 0
#non so se posso metterlo qui, perchè non c'è dentro gurobi -> cambia pazienti primi e basta
t={}
for i in istanza.pazientiPrimi:
    t[i]=model.addVar(vtype=grb.GRB.CONTINUOUS, name=f't({i})',lb=0.0)
    model.update()
#print(t)

#creazione variabili z[i] ritardo fra l[i] e t[i] -> il modello me lo fa mettere su P'
#ma in realtà io ho l solo su P e in più sui secondi servizi non si può generare ritardo per il vincolo di d
#non ha manco senso lo 0
#ho capito dalla sol che secondo me l è la fine di entrambi i servizi (quindi metto l per i doppi pari a l dei primi)
z={}
for i in istanza.pazientiPrimi:
    z[i]=model.addVar(vtype=grb.GRB.CONTINUOUS, name=f'z({i})',lb=0.0)
    model.update()
#print(z)

#variabile continua D per catturare il massimo ritardo e rendere lineare il vincolo di min(max)
D=model.addVar(vtype=grb.GRB.CONTINUOUS, name=f'D',lb=0.0)
model.update()
#print(D)

#-------------------------------------VINCOLI-----------------------------------------------
#------------------------------come il modello classico------------------------------------------

#vincolo 2 -per catturare il massimo ritardo (ciclo su tutti i pazienti, anche i doppi dove secondo me non c'è ritardo)
for i in istanza.pazientiPrimi:
    model.addConstr(D>=z[i],name=f'maxRitardo_{z[i].VarName}')
    model.update()

#vincolo 3 - per tutti i k, per tutti i pazienti visitabili da k (secondo me in P', secondo il modello in P),
# sommando su tutti le variabili che dicono se un paziente è visitato esattamente prima di i deve fare 1
#quindi o un generico j paziente visitabile è visitato prima di i (fra j c'è anche lo 0 magazzino)
#oppure vale 1 x[i][i][k] che significa che k NON visita i
for k in istanza.caregivers:
    for i in istanza.pazientiVisitabili[istanza.caregivers.index(k)]:
        model.addConstr(grb.quicksum(x[j,i,k] for j in istanza.pazientiVisitabili[istanza.caregivers.index(k)]) == 1)
        model.update()
#rimane la possibilità che un k visiti paziente e paziente' -> va tolta con il vincolo 9 penso
#continuo a essere convinta che si debba ciclare su P' e non su P (nella spiegazione mette P')

#vincolo 4 - continuità del flusso
#se k arriva in i da un generico j allora ripartirà da i e andrà in un altro generico j
#devo togliere i e j uguali perchè sono a 1 se k non lo visita
#nel file mette i - e lo mette uguale a 0 (pace capiscilo lo stesso)
for k in istanza.caregivers:
    for i in istanza.pazientiVisitabili[istanza.caregivers.index(k)]:
        model.addConstr(grb.quicksum(x[j,i,k] for j in istanza.pazientiVisitabili[istanza.caregivers.index(k)] if j!=i)
                        == grb.quicksum(x[i,j,k] for j in istanza.pazientiVisitabili[istanza.caregivers.index(k)] if j!=i))
        model.update()

#vincolo 5 - z[i] sono i ritardi (li metti >= tanto poi minimizzi quindi verranno =)
#li ho costruiti per tutti i pazienti anche i doppi, tendo come l del doppio lo stesso l del paziente
#significa che nella finestra di tempo e-l devi erogare sia il primo che il secondo servizio
#non so se è giusto ma interpretando la soluzione del grafico secondo me fa così
for i in istanza.pazientiPrimi:
    model.addConstr(z[i]>=t[i]-istanza.l[i])
    model.update()

#vincolo 6 - se un k serve in sequenza i e j (quindi x[i][j][k]=1) allora il t[j] deve essere almeno pari al
#t[i] + durataServizio[i] + distanza[i][j]
#se non si attiva il vincolo allora t[j] non deve avere "blocchi", per cui posso mettere che sia >=0 o numero negativo
#per fare questo fisso M abbastanza alta -> se esagero viene t[j]>= numero negativo che va bene
#basterebbe mettere che M sia pari a t[i] + durataServizio[i] + distanza[i][j] ma per non calcolare sempre
# mi faccio una volta i max si tutti
M = sum(istanza.durataVisita.values()) + sum(sum(subdict.values()) for subdict in istanza.distanzeDict.values())
#forse è un pò esagerato non so se crea problemi
#è come se faccesse tutte le visite 1 solo k, però sommando così la distanze ti viene na roba enorme


for k in istanza.caregivers:
    for i in istanza.pazientiVisitabili[istanza.caregivers.index(k)][1:]:
        for j in istanza.pazientiVisitabili[istanza.caregivers.index(k)][1:]:
            if i != j:
                # print(istanza.durataVisita[i])
                # print(istanza.distanzeDict[i][j])
                # print(M)
                # print(x[i,j,k])
                model.addConstr(t[j]>=t[i]+istanza.durataVisita[i]+istanza.distanzeDict[i][j]-M+M*x[i,j,k])
                #non file do output del modello fa la somma dei numeri quidi vedi 1 solo addendo
                model.update()

#problema parte da j =0 e i =0 ma i tempi sono solo per i pazienti
#mi verrebbe da mettere due if e levare gli 0 ma ho paura che poi non torni con tutti i casi x(ijk)
#quando fai i=p1 e salta lo j=0 poco male perchè non ho il tempo di inizio t[0] che corrisponderebbe all'arrivo in magazzino
#quadno hai i=0 e j=p1 ti serve avere il vincolo che t1 non può iniziare prima del tempo in cui il caregiver va dal magazzino al p1
#quindi serve (dovrei mettere durata visita di 0 = 0) e un t[0]=0

#provo lasciando il vincolo di prima per tutti i pazienti p
#introduco il vincolo che i pazienit visitati per primi, quindi quelli che hanno 0jk devono avere un tempo di inizio j
#almeno ari pari alla distanza fra il magazzino e il paziento
#ovviamento solo se il p j-esimo è visitato dopo lo 0, quindi ritorna la M

for k in istanza.caregivers:
        for j in istanza.pazientiVisitabili[istanza.caregivers.index(k)][1:]:
                model.addConstr(t[j]>=istanza.distanzeDaZero[j]-M+M*x["0",j,k])
                #non file do output del modello fa la somma dei numeri quidi vedi 1 solo addendo
                model.update()


#vincolo 7- per ogni paziente con due servizi, impongo ch eil secondo servizio (ovvero t[i] del paziente doppio) sia
#compreso fra il ritardo mimimo e massimo a cui pososno essere erogati i servizi
#per i servizi in contemporanea metto 0 sia a dmin che a dmax
for j in istanza.pazientiDoppi:
    indice=istanza.pazientiDoppi.index(j)
    model.addConstr(istanza.dmin[indice]<=t[j]-t[istanza.pazientiDueServizi[indice]])
    model.addConstr(t[j]-t[istanza.pazientiDueServizi[indice]]<=istanza.dmax[indice])
    model.update()

#vincolo 8 - un caregiver per servire dei pazienti deve partire dalla centrale
#se x["0","0",k]=1, quindi il k non parte, allora nessuna variabile a lui associata può valere 1
for k in istanza.caregivers:
    for i in istanza.pazientiVisitabili[istanza.caregivers.index(k)]:
        for j in istanza.pazientiVisitabili[istanza.caregivers.index(k)]:
            if i!=j:
                model.addConstr(x[i,j,k]<=1-x["0","0",k])
                model.update()

#vincolo 9 - i pazienti che ricevono due servizi devono esser serviti da 2 k diversi (imposto dal problema)
#per ogni k e per ogni paziente che richiede due servizi
#se k può servirlo
#cerchi il doppio del paziente i -> j
#se k può servire ance j allora devi imporre che o serve i o serve j
#sommi su tutti i pazienti l servibili prima di i + tutti gli l servibili vero j e lo metti <=1
#o serve i o serve j
for k in istanza.caregivers:
        for i in istanza.pazientiDueServizi:
            if i in istanza.pazientiVisitabili[istanza.caregivers.index(k)]:
                indice = istanza.pazientiDueServizi.index(i)
                j=istanza.pazientiDoppi[indice]
                if j in istanza.pazientiVisitabili[istanza.caregivers.index(k)]:
                    model.addConstr((grb.quicksum(x[l,i,k] for l in istanza.pazientiVisitabili[istanza.caregivers.index(k)] if l!=i)) +
                                (grb.quicksum(x[l,j,k] for l in istanza.pazientiVisitabili[istanza.caregivers.index(k)] if l!=j))<=1)

#vincolo 10 x binarie messo

#vincolo 11
for i in istanza.pazientiPrimi:
    model.addConstr(t[i]>=istanza.e[i])

model.update()

#vincolo 12 e vincolo 13 secondo me sono di default nelle variabili gurobi


#vincolo tutti i pazienti devono essere visitati
for j in istanza.pazientiPrimi:
    model.addConstr(grb.quicksum(x[i,j,k]
                                 for i in istanza.pazientiPrimi+["0"]
                                 for k in istanza.caregivers
                                 if i!=j
                                 if i in istanza.pazientiVisitabili[istanza.caregivers.index(k)]
                                 if j in istanza.pazientiVisitabili[istanza.caregivers.index(k)]
                                 )==1 )





#----------------------------------------------FUNZIONE OBBIETTIVO--------------------------------
#------------------------------------------------modificata-----------------------------------------------
a=1/3
b=1/3
c=1/3
#il problema è che nel modello classico la matrice delle distanze è simmetrica quindi per calcolare le distanze
#riferite alle variabili x(ijk) possono invertire i e j a mio piaciamento -> serve per le distanze da magazzino
#devo contare sia "andata" che "ritorno"
#in questo dataset le distanze sono reali, quindi non simmetriche
#nella lettura del file ho modificato i dizionari distanzeDcit e distanzeDaZero in modo tale da avere
#tutte le distanze da usare nella f. obbiettivo
#primo addendo è per andare da 0 al primo paziente
#poi da paziente a paziente
#ultimo addendo è da paziente a 0 -> rientro in magazzino


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
                       grb.quicksum(istanza.distanzeDict[i]['0'] * x[i, "0", k]
                                    for i in istanza.pazientiPrimi
                                    for k in istanza.caregivers
                                    if i in istanza.pazientiVisitabili[istanza.caregivers.index(k)])
                       ),

                   grb.GRB.MINIMIZE)


model.update()
# fa un file dove scrive tutte le variabili e i vincoli del problema
# model.write("modello.lp")


# Imposta il limite di tempo di 120 secondi (2 minuti)
model.setParam('TimeLimit', 120)

model.optimize()

# STAMPA --------------------------------------------------------------------------------------------------
# Verifica se è stata trovata una soluzione (ottima o meno)
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
    # print("\n-> Variabili x[i,j,k] attive:")
    # for (i, j, k), var in x.items():
    #     if i!=j: #non stampo quelle a 1 con i=j perchè sono quando k NON va dai pazienti
    #         if var.X > 0.5:  # è binaria quindi basta > 0.5
    #             if i=='0':
    #              print(f"x({i},{j},{k}) = {int(var.X)}")
    #             else:
    #                 print(f"x({i},{j},{k}) = {int(var.X)}")

    # Stampa percorsi ordinati per ogni caregiver
    print("\n-> Percorsi per caregiver:")
    for k in istanza.caregivers:
        percorso = []
        corrente = "0"  # partenza dal magazzino
        visitati = set()

        while True:
            trovato_prossimo = False
            for j in istanza.pazientiVisitabili[istanza.caregivers.index(k)] + ["0"]:
                if (corrente, j, k) in x and x[corrente, j, k].X > 0.5:
                    percorso.append((corrente))
                    if j == "0":  # ritorno al magazzino
                        trovato_prossimo = False
                        break
                    corrente = j
                    if corrente in visitati:
                        break  # evitiamo cicli infiniti
                    visitati.add(corrente)
                    trovato_prossimo = True
                    break
            if not trovato_prossimo:
                break

        if percorso:
            percorso_str=""
            for i in percorso:
                percorso_str += f'{i} -> '
            percorso_str += "0"
            print(f"Caregiver {k}: {percorso_str}")

#----------tolta tutta la stampa tanto non ho le soluzioni dettagliate come in mankowska-------------------
    # Stampa tempi di inizio visita
    # print("\n-> Tempi di inizio visita t[i]:")
    # for i, var in t.items():
    #     print(f"t({i}) = {var.X:.2f}")

    # Stampa ritardi z[i]
    # print("\n-> Ritardi z[i]:")
    # somma_ritardi=0
    # for i, var in z.items():
    #     somma_ritardi += var.X
    #     print(f"z({i}) = {var.X:.2f}")

    # TANTO NON CI SONO LE SOLUZIONI
    # Calcolo e stampa della distanza totale percorsa
    # distanza_totale = 0
    # for (i, j, k), var in x.items():
    #     if var.X > 0.5:
    #         if i == "0":
    #             distanza = istanza.distanzeDaZero[j]
    #         elif j == "0":
    #             distanza = istanza.distanzeDaZero[i]
    #         else:
    #             distanza = istanza.distanzeDict[i][j]
    #         distanza_totale += distanza
    # print(f"\nDistanza totale percorsa: {distanza_totale:.3f}")
    # Stampa massimo ritardo D
    # print(f"Massimo ritardo Dmax = {D.X:.3f}")
    #Stampa somma dei ritardi
    # print (f'Somma dei singoli ritardi: {somma_ritardi:.3f}')


    # Stampa valore della funzione obiettivo
    print(f"\nValore funzione obiettivo: {model.ObjVal:.3f}")

else:
    print("Non è stata trovata una soluzione ottima.")
