import gurobipy as grb
from itertools import product
# Parametri
n = m = 3  # n jobs, m machines

times = [[2, 1, 2],  # tempi di ogni job su ogni macchina
         [1, 2, 2],
         [1, 2, 1]]

M = sum(times[i][j] for i in range(n) for j in range(m))  # Big M

machines = [[2, 0, 1],  # ordine dei job sulle macchine
            [1, 2, 0],
            [2, 1, 0]]

# Creazione del modello Gurobi
model = grb.Model('JSSP')

# Variabile C (makespan da minimizzare)
c = model.addVar(name="C")

# Variabili x[j][i] che rappresentano il tempo di inizio del job j sulla macchina i
x = [[model.addVar(name=f'x({j+1},{i+1})') for i in range(m)] for j in range(n)]

# Variabili y[j][k][i] binarie che valgono 1 se j precede k sulla macchina i
y = [[[model.addVar(vtype=grb.GRB.BINARY, name=f'y({j+1},{k+1},{i+1})') for i in range(m)] for k in range(n)] for j in range(n)]

# Obiettivo: Minimizzare il makespan
model.setObjective(c, grb.GRB.MINIMIZE)

# Vincoli: puoi iniziare il job j su i solo se lo hai finito su i-1
for j, i in product(range(n), range(1, m)):
    model.addConstr(x[j][machines[j][i]] - x[j][machines[j][i - 1]] >= times[j][machines[j][i - 1]],
                    name=f"start_after_{j+1}_{i+1}")

# Vincoli di non sovrapposizione: non accavallare i job sulle macchine
for j, k in product(range(n), range(n)):
    if k != j:
        for i in range(m):
            model.addConstr(x[j][i] - x[k][i] + M * y[j][k][i] >= times[k][i],
                            name=f"no_overlap_{j+1}_{k+1}_{i+1}")
            model.addConstr(-x[j][i] + x[k][i] - M * y[j][k][i] >= times[j][i] - M,
                            name=f"no_overlap_reverse_{j+1}_{k+1}_{i+1}")

# Vincoli di makespan: c maggiore di tutti i tempi di completamento dei lavori
for j in range(n):
    model.addConstr(c - x[j][machines[j][m - 1]] >= times[j][machines[j][m - 1]],
                    name=f"makespan_constraint_{j+1}")

# Ottimizzazione del modello
model.optimize()

# Stampa del risultato
if model.status == grb.GRB.OPTIMAL:
    print("Completion time: ", c.x)
    for j, i in product(range(n), range(m)):
        print(f"Task {j+1} starts on machine {i+1} at time {x[j][i].x}")
else:
    print("No optimal solution found.")
