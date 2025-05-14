import gurobipy as grb
from itertools import product

# Definizione dei pazienti
nP = 6 #Pazienti totali
nD = 3 #i doppi
k=3 #caregivers
s=3 #numero dei servizi

P=["0","P1","P2","P3","P4","P5","P6"] #pazienti
Pp=["0","P1","P2","P3","P4","P5","P6", "P4'", "P5'","P6'"] #pazienti primi
Pr=[("P4","P4'"), ("P5","P5'"), ("P6","P6'")] #tuple vincoli di precendenza


#Definizione dei caregivers
C=["C1","C2","C3"]

#Definizione dei servizi
S=["S1","S2","S3"]


Ppk=[["0","P1","P3","P4","P5","P6"],
     ["0","P2", "P4'", "P5'","P6'"],
     ["0","P1","P2","P3","P4", "P4'", "P5'","P6'"]]

#Associazione caregivers -> pazienti
#faccio una prova senza i servizi, il punto è poi creare o tante liste Pk dove ogni caregivers ha elenco dei suili pazienzti
#oppure un dizionario dove metti chiave il caregivers e valore la lista con tutti i pazienti



# distanze
d = {('0', 'P1'): 10, ('0', 'P2'): 20, ('0', 'P2'): 30,('0', 'P4'): 10,
    ('P1', 'P2'): 10, ('P1', 'P3'): 20, ('P1', 'P4'): 30,
     ('P2', 'P1'): 10, ('P2', 'P3'): 15, ('P2', 'P4'): 25,
     ('P3', 'P1'): 20, ('P3', 'P2'): 15, ('P3', 'P4'): 10,
     ('P4', 'P1'): 30, ('P4', 'P2'): 25, ('P4', 'P3'): 10}  # Tempi di viaggio

dists = [[15, 20, 20, 5],
         [15,30,15,20],
         [20,15,5],
         [5]]
#tempo di servizio
tempi=[0,20,30,25,15]

e = {'P1': 8*60, 'P2': 9*60, 'P3': 10*60, 'P4': 11*60}  # Tempi di inizio più presto
l = {'P1': 10*60, 'P2': 11*60, 'P3': 12*60, 'P4': 13*60}  # Tempi di inizio più tardi


# number of nodes and list of vertices
n = len(dists)  # number of cities to visit
V = set(range(len(dists)))  # set of all cities (nodes)

# distances matrix -> we need to complete the matrix of distances
# c = [[0 if i == j  # same city distance = 0
#       else dists[i][j-i-1] if j > i  # upper triangular matrix
#       else dists[j][i-j-1]  # lower triangular matrix (symmetry)
#       for j in V] for i in V]

# Modello Gurobi
model = grb.Model("HHC_Routing_Scheduling")

# variabili x ijk binarie se k visita i e poi j =1, se i=j vale 1 quando k non visita i
# Ciclo su C e per ogni k in C
for k in C:
    # Per ogni valore in Ppk associato a k
    for i in Ppk[C.index(k)]:
        # Per ogni valore in Ppk associato a k
        for j in Ppk[C.index(k)]:
            # Creazione della variabile e assegnazione del nome
            var_name = f'x_{i}_{j}_{k}'  # Nome della variabile
            x = model.addVar(vtype=grb.GRB.BINARY, name=var_name)
            #devi fare delle liste di liste non metterle a caso



#varibili ti che indicano il tempo a cui parte la somministrazione del servizio per ogni paziene
t = [model.addVar(vtype=grb.GRB.CONTINUOUS, name=f't_{p}')for p in Pp]

#varibili ti che indicano il ritardo per ogni paziente (secondo me puoi mettere su P e non Pp perchè tanto
#non puoi fare ritardo sui secondi servizi e in più non hai l per i secondi servizi)

z= [model.addVar(vtype=grb.GRB.CONTINUOUS, name=f'z_{p}') for p in P]

#D è per im min-max, serve a catturare il massimo ritardo
D=model.addVar(vtype=grb.GRB.CONTINUOUS, name="D")

# D maggiore di tutte le z[p] che indicano i ritardi (se z lo fai su Pp poi itera su P)
for p in P:
    model.addConstr(D>=z[p]) #io non so se posso dire z[p] o se devo iterare sugli indici

# Objective function: minimize the distance traveled
model.setObjective(grb.quicksum(c[i][j] * x[i, j] for i in V for j in V), grb.GRB.MINIMIZE)

# Constraint: each city must be left exactly once
for i in V:
    model.addConstr(grb.quicksum(x[i, j] for j in V if i != j) == 1)

# Constraint: each city must be entered exactly once
for j in V:
    model.addConstr(grb.quicksum(x[i, j] for i in V if i != j) == 1)

# Subtour elimination constraint (using the y variables)
for i, j in product(V - {0}, V - {0}):  # excluding city 0
    if i != j:
        model.addConstr(y[i] - (n+1) * x[i, j] >= y[j] - n)

# Optimize the model
model.optimize()

# Checking if a solution was found
if model.status == grb.GRB.OPTIMAL:
    print(f'Route with total distance {model.objVal} found: {places[0]}')
    nc = 0  # Start from the first city (index 0)
    while True:
        # Find the next city by looking for the arc with x[nc][i] = 1
        nc = [i for i in V if x[nc, i].x >= 0.99][0]
        print(f' -> {places[nc]}', end='')  # Print the city name
        if nc == 0:  # If we return to the starting city, we're done
            break
    print()  # New line after printing the entire route
else:
    print("No optimal solution found.")
