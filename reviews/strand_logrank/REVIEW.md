# Revisión: dos lemas sobre la log-rank aplicada a diagramas de persistencia (STRAND)

**Alcance.** Reviso los dos lemas tal como están enunciados en la petición.
No pude abrir arXiv:2606.11911 desde este entorno (arxiv.org no está en la red
permitida de la sesión). No afirmo nada sobre el contenido del artículo.

**Verificación.** `check_lemmas.py` lo calcula todo con aritmética racional
exacta (`fractions.Fraction`). Por eso cada igualdad que se comprueba es una
identidad exacta y no una coincidencia con tolerancia. U se calcula siempre con
la definición log-rank, nunca a partir de los S_k. La salida completa está en
`output.txt`, y `tests/test_strand_logrank.py` repite las comprobaciones con 36
conjuntos de datos aleatorios.

```bash
python reviews/strand_logrank/check_lemmas.py
pytest tests/test_strand_logrank.py
```

---

## 0. Notación y convenciones

Fijo todas las convenciones, porque los dos lemas dependen de ellas.

- Rasgos i = 1, …, N. Cada uno tiene un tiempo observado tᵢ > 0, un indicador
  δᵢ ∈ {0, 1} (1 = evento) y un diagrama k(i). Sin censura, δᵢ = 1 para todo i.
- El diagrama k tiene m_k ≥ 0 rasgos (se permite m_k = 0), y N = Σ_k m_k.
  Todos los rasgos de un diagrama comparten el grupo del diagrama.
  N_A = Σ_{k∈A} m_k.
- τ₁ < τ₂ < … < τ_J son los tiempos de evento **distintos**.
- d_j = #{i : tᵢ = τ_j, δᵢ = 1} y **n_j = #{i : tᵢ ≥ τ_j}**. d_{Aj} y n_{Aj}
  son las mismas cuentas restringidas a los rasgos de A.
- Λ̂(t) = Σ_{j : τ_j ≤ t} d_j / n_j: Nelson–Aalen agrupado, continuo por la derecha.
- M̂ᵢ = δᵢ − Λ̂(tᵢ), que sin censura es 1 − Λ̂(tᵢ). S_k = Σ_{i∈k} M̂ᵢ.
- U = Σ_j (d_{Aj} − n_{Aj} d_j / n_j).

### 0.1 Por qué n_j = #{i : tᵢ ≥ τ_j}

1. El conjunto de riesgo en τ_j está formado por los rasgos que siguen
   "vivos", es decir, que no han muerto ni han sido censurados, *justo antes*
   de τ_j. En notación de procesos de conteo es n_j = Σᵢ Yᵢ(τ_j) con
   Yᵢ(t) = 1{tᵢ ≥ t}. Este proceso es continuo por la izquierda, y por eso es
   predecible.
2. Un rasgo con tᵢ = τ_j estaba vivo justo antes de τ_j, así que pertenece al
   conjunto de riesgo en τ_j. Por eso se usa ≥ y no >. Con > el último tiempo
   tendría n_J = 0 y el cociente d_J/n_J no estaría definido. Además, en
   general d_j podría superar a n_j.
3. **Sin censura**, n_j = N − Σ_{l<j} d_l. Prueba: todo tᵢ es algún τ_l
   (no hay tiempos de censura). Entonces {i : tᵢ < τ_j} = ⋃_{l<j} {i : tᵢ = τ_l},
   que es una unión disjunta de cardinal Σ_{l<j} d_l. Su complemento es
   {i : tᵢ ≥ τ_j}.
4. Empates: si d_j ≥ 2, los d_j rasgos empatados están todos en riesgo en τ_j
   y salen todos a la vez. Ninguna demostración de abajo supone d_j = 1.

### 0.2 Lema 0 (intercambio de sumas)

Para cualquier subconjunto G de rasgos,

  Σ_{i∈G} Λ̂(tᵢ) = Σ_j (d_j / n_j) · #{i ∈ G : tᵢ ≥ τ_j}.

*Demostración.* Λ̂(tᵢ) = Σ_j (d_j/n_j)·1{τ_j ≤ tᵢ}. La suma doble es finita,
así que se puede intercambiar, y 1{τ_j ≤ tᵢ} = 1{tᵢ ≥ τ_j}. ∎

Aquí se ve por qué las dos convenciones tienen que ir juntas. El "≤" de Λ̂ y
el "≥" de n_j producen el **mismo** indicador. Si una de las dos cambia, la
identidad se rompe (contraejemplos en §1.4).

---

## 1. Lema 1

### 1.1 Proposición

(a) Σᵢ M̂ᵢ = 0, y por tanto Σ_k S_k = 0.
(b) U = Σ_{i∈A} M̂ᵢ = Σ_{k∈A} S_k.

### 1.2 Hipótesis

- **H1** No hay censura: δᵢ = 1 para todo i. Hay que excluir *todas* las barras
  infinitas, no solo la de H0 (ver §3.2).
- **H2** El incremento de Λ̂ es d_j/n_j, que es el Nelson–Aalen agrupado o de
  Breslow, y no la corrección de Fleming–Harrington. Λ̂ se evalúa en tᵢ, no en tᵢ−.
- **H3** n_j = #{i : tᵢ ≥ τ_j} y n_{Aj} = #{i ∈ A : tᵢ ≥ τ_j}. Λ̂ se calcula
  con la muestra conjunta.
- **H4** La etiqueta de grupo es del diagrama.

### 1.3 Demostración

1. Por el Lema 0 con G = todos los rasgos, Σᵢ Λ̂(tᵢ) = Σ_j (d_j/n_j)·n_j = Σ_j d_j.
2. Sin censura (H1), cada rasgo muere en exactamente un τ_j, así que
   Σ_j d_j = N. Por tanto Σᵢ Λ̂(tᵢ) = N. Este es el paso de la prueba
   propuesta, y es correcto.
3. Σᵢ M̂ᵢ = Σᵢ 1 − Σᵢ Λ̂(tᵢ) = N − N = 0.
4. Los diagramas forman una partición de los rasgos, así que
   Σ_k S_k = Σᵢ M̂ᵢ = 0. Un diagrama vacío aporta S_k = 0. Esto prueba (a).
5. Por el Lema 0 con G = A, Σ_{i∈A} Λ̂(tᵢ) = Σ_j (d_j/n_j)·n_{Aj}.
6. Sin censura, cada rasgo de A muere en exactamente un τ_j, así que
   Σ_{i∈A} 1 = N_A = Σ_j d_{Aj}.
7. Restando 6 − 5: Σ_{i∈A} M̂ᵢ = Σ_j d_{Aj} − Σ_j n_{Aj} d_j/n_j = U.
8. Por H4, los rasgos de A son la unión disjunta de los rasgos de los
   diagramas k ∈ A. Por tanto Σ_{i∈A} M̂ᵢ = Σ_{k∈A} S_k. Esto prueba (b). ∎

**Sobre la prueba propuesta.** "Intercambiar sumas y usar Σᵢ Λ̂(tᵢ) = N"
demuestra (a) completa. Para (b) no basta con eso: hace falta la versión
restringida al grupo A (pasos 5 y 6). Es una laguna, no un error.

**Generalización con censura.** Si M̂ᵢ = δᵢ − Λ̂(tᵢ), los pasos 1 a 8 valen
igual: en el paso 2 se usa Σ_j d_j = Σᵢ δᵢ, y en el paso 6
Σ_j d_{Aj} = Σ_{i∈A} δᵢ. H1 solo hace falta para que el residuo se pueda
escribir como **1** − Λ̂.

### 1.4 Contraejemplos (las hipótesis son necesarias)

Los cuatro están en el script, apartados (a) a (c).

| Qué se cambia | Datos | U real | Lo que da la fórmula |
|---|---|---|---|
| Censura con M̂ = 1 − Λ̂ | t = (1 evento, 2 censurado), un rasgo por diagrama, A = {2} | −1/2 | Σ_A = +1/2 y Σ_k = 1 ≠ 0. Con δ − Λ̂ sale −1/2 y 0, correcto |
| Empates con Fleming–Harrington | t = (1, 1), A = {1} | 0 | Λ̂(1) = 1/2 + 1 = 3/2, M̂ = (−1/2, −1/2), Σ = −1 |
| Λ̂(tᵢ−) en lugar de Λ̂(tᵢ) | t = (1, 2), A = {1} | 1/2 | M̂ = (1, 1/2): Σ_A = 1 y Σ = 3/2 |
| n_j con ">" | cualquiera | — | n_J = 0 en el último tiempo, así que Λ̂ no está definido |

### 1.5 Verificación numérica

K = 8 con m = (3, 5, 2, 4, 1, 6, 3, 4), N = 28. Las persistencias son
scale_k · Exp(1), con una escala distinta en cada diagrama para que haya
dependencia dentro del diagrama.

- **Caso 1, sin empates:** en las 70 asignaciones, U (por definición) = Σ_{k∈A} S_k, de forma exacta. Σ_k S_k = 0, también exacto.
- **Caso 2, con empates:** las persistencias se redondean hacia arriba a enteros, lo que produce muchos empates. Mismo resultado.
- **Tests:** 24 conjuntos aleatorios, con K entre 2 y 8, n_A aleatorio, m_k entre 0 y 5, con y sin empates. Además, 6 conjuntos con censura y residuos δ − Λ̂.

### 1.6 Veredicto

**Correcto bajo H1 a H4.** La prueba propuesta va en la dirección buena, pero
le falta la versión del intercambio restringida al grupo A. Las convenciones H2
y H3 no son de detalle: si cualquiera de ellas cambia, el lema es falso. La
identidad es la versión de dos grupos de un hecho clásico: el score de Cox con
covariable binaria en β = 0 y empates de Breslow vale Σᵢ Zᵢ M̂ᵢ (ver §5).

---

## 2. Lema 2

### 2.1 Proposición

Sean K ≥ 2 y 1 ≤ n_A ≤ K − 1. Sea A* un subconjunto de tamaño n_A elegido
uniformemente al azar entre los C(K, n_A) posibles, con los diagramas fijos.
Entonces:

(a) Λ̂, los M̂ᵢ y los S_k no dependen de A*.
(b) U(A*) = Σ_{k∈A*} S_k es el total de una muestra aleatoria simple sin
reemplazo de tamaño n_A, tomada de la población finita {S₁, …, S_K}.
(c) E[U] = 0 y Var(U) = n_A n_B Σ_k S_k² / (K(K − 1)).

### 2.2 Hipótesis

- H1 a H4 del Lema 1.
- **H5** Esquema de permutación: n_A es fijo y todas las asignaciones son
  equiprobables. Equivale a permutar al azar el vector de etiquetas de los
  diagramas.
- **H6** Bajo H0, los K diagramas son intercambiables, por ejemplo i.i.d.
  H6 solo hace falta para que la *prueba* sea exacta, no para la fórmula, que
  es un cálculo condicional a los datos. La intercambiabilidad se pide a nivel
  de diagrama: los rasgos de un mismo diagrama pueden ser dependientes de
  cualquier forma.

### 2.3 Demostración

1. d_j y n_j son cuentas sobre la muestra conjunta, así que Λ̂ depende de los
   datos solo a través del multiconjunto {tᵢ}, que no cambia con A*. Por tanto
   M̂ᵢ = 1 − Λ̂(tᵢ) y S_k = Σ_{i∈k} M̂ᵢ son funciones de los diagramas y no de
   las etiquetas. En cambio, n_{Aj} y d_{Aj} sí dependen de A*, pero no entran
   en Λ̂. Esto prueba (a).
2. El Lema 1 vale para **cualquier** subconjunto A de diagramas. Entonces
   U(A*) = Σ_k I_k S_k con I_k = 1{k ∈ A*}. Esto prueba (b).
3. P(I_k = 1) = C(K−1, n_A−1)/C(K, n_A) = n_A/K. Para k ≠ l,
   P(I_k = I_l = 1) = C(K−2, n_A−2)/C(K, n_A) = n_A(n_A − 1)/(K(K − 1)).
4. De ahí, Var(I_k) = (n_A/K)(n_B/K) = n_A n_B/K² y
   Cov(I_k, I_l) = n_A(n_A−1)/(K(K−1)) − n_A²/K² = −n_A n_B/(K²(K − 1)).
5. E[U] = (n_A/K) Σ_k S_k = 0 por el Lema 1(a).
6. Var(U) = Σ_k S_k² Var(I_k) + Σ_{k≠l} S_k S_l Cov(I_k, I_l)
   = (n_A n_B/K²) [Σ_k S_k² − (1/(K−1)) Σ_{k≠l} S_k S_l].
7. Σ_{k≠l} S_k S_l = (Σ_k S_k)² − Σ_k S_k² = −Σ_k S_k², otra vez por el Lema 1(a).
8. Var(U) = (n_A n_B/K²) Σ_k S_k² · (1 + 1/(K−1)) = n_A n_B Σ_k S_k² / (K(K − 1)). ∎

**Forma general**, sin usar Σ S_k = 0:
Var(U) = n_A (1 − n_A/K) s², con s² = Σ_k (S_k − S̄)²/(K − 1). Es la varianza
de libro del total muestral sin reemplazo, con corrección por población finita.
Con S̄ = 0 coincide con (c).

### 2.4 Observaciones de rigor

- La fórmula da la varianza **exacta** de la distribución de permutación,
  condicional a los datos, para todo K ≥ 2. No es una aproximación asintótica.
- La normalidad de U/√Var(U) es otro asunto. Requiere condiciones de tipo
  Hájek: n_A, n_B → ∞ y max_k S_k² / Σ_k S_k² → 0. No forma parte del lema.
- "Λ̂ no cambia" es cierto porque Λ̂ se calcula con la muestra conjunta. Si se
  estratificara o se calculara por grupo, sería falso.
- Hay que permutar **diagramas** enteros. Si se permutan rasgos, la varianza
  pasa a ser N_A N_B Σᵢ M̂ᵢ²/(N(N − 1)) y se pierde la protección frente a la
  dependencia dentro de cada diagrama.
- El lema sigue valiendo con censura si M̂ᵢ = δᵢ − Λ̂(tᵢ) (apartado (f) del
  script). Entonces H6 incluye el mecanismo de censura: lo que se intercambia
  es el diagrama entero, con sus pares (tᵢ, δᵢ). La validez de la prueba de
  permutación no necesita censura no informativa, solo intercambiabilidad.

### 2.5 Verificación numérica

En las dos columnas se enumeran las 70 asignaciones y la varianza se divide
entre 70.

| | Caso 1 (sin empates) | Caso 2 (con empates) |
|---|---|---|
| E_perm[U] | 0 (exacto) | 0 (exacto) |
| Var_perm(U) por enumeración | 12.008356 | 6.088008 |
| n_A n_B Σ S_k² / (K(K−1)) | 12.008356 (igualdad exacta) | 6.088008 (igualdad exacta) |
| Error típico: dividir entre 69 | 12.182390 | 6.176240 |

Las 70 asignaciones **son** la distribución completa, así que la varianza
"empírica" se divide entre 70. Si se divide entre 69 (`ddof=1`), aparece un
factor espurio 70/69.

### 2.6 Veredicto

**Correcto bajo H1 a H5.** H6 hace falta para que la prueba sea exacta, no
para la fórmula. El resultado es la combinación del Lema 1 con la varianza
clásica del muestreo sin reemplazo.

---

## 3. Casos límite

### 3.1 Tabla

| Caso | Lema 1 | Lema 2 | Comentario |
|---|---|---|---|
| Censura, M̂ = 1 − Λ̂ | **Falla**: Σ M̂ = número de censurados | **Falla** | Contraejemplo §1.4. Comprobado en los tests |
| Censura, M̂ = δ − Λ̂ | Vale | Vale | Apartado (f) del script |
| m_k = 0 | Vale (S_k = 0) | Vale; el diagrama cuenta en K y en n_A | Apartado (e) |
| m_k = 1 para todo k | Log-rank clásico, equivalente a la prueba de Savage | Permutación clásica; además Var(U) = E_perm[V] (§4) | Apartado (d) |
| Todos los tiempos empatados | Trivial (M̂ ≡ 0) | Var = 0 | V = 0 y κ = 0/0. Apartado (h) |
| K = 1 | Trivial | Fórmula indefinida (0/0) | No hay prueba posible |
| K pequeño | Vale | Fórmula exacta, pero la distribución es muy discreta | Ver abajo |

**K pequeño.** El p-valor exacto de permutación vale como mínimo 1/C(K, n_A).
Si n_A = n_B, vale como mínimo 2/C(K, n_A), porque U(Aᶜ) = −U(A) por el Lema 1(a).

- K = 4 (2 + 2): p ≥ 1/3. En el apartado (g), los 6 valores de U salen en parejas ±.
- K = 6: p ≥ 1/15 ≈ 0.067 con cualquier reparto.
- K = 7: p ≥ 1/35 ≈ 0.029 (3 + 4) y p ≥ 1/21 ≈ 0.048 (2 + 5).
- K = 8 (4 + 4): p ≥ 2/70 ≈ 0.029.

Por tanto, una prueba bilateral al 5 % necesita **K ≥ 7**. Con K pequeño
tampoco tiene sentido aproximar U/√Var(U) por una normal: hay que enumerar.

### 3.2 Barras infinitas

- **H0.** En un complejo final conexo hay exactamente una barra infinita por
  diagrama. Quitarla elimina un rasgo por diagrama de forma independiente de
  las etiquetas, así que es legítimo. Si el complejo final no es conexo (por
  ejemplo, Rips truncado en r_max), hay más de una barra infinita en H0.
- **H_q con q ≥ 1, o filtración truncada.** Las clases que siguen vivas al
  final de la filtración son **censuras por la derecha**, con tiempo de
  censura cᵢ = r_max − bᵢ. Excluir solo la barra de H0 no basta para que se
  cumpla H1. Lo correcto es excluirlas todas, y entonces la prueba compara
  solo persistencias finitas, o tratarlas como censuradas y usar residuos
  δ − Λ̂.
- **Sustituir ∞ por un tope y tratarlo como evento.** Crea muertes ficticias y
  un bloque de empates en el tope. El álgebra de los lemas sigue valiendo,
  pero cambia lo que se está estimando.
- Ojo: cᵢ = r_max − bᵢ depende del nacimiento. Si nacimiento y persistencia
  están correlacionados, la censura no es independiente. Esto afecta a la
  interpretación de Λ̂, pero no a la validez de la permutación por diagramas
  (§2.4).

---

## 4. Varianza hipergeométrica V y κ

### 4.1 Definiciones

  V = Σ_{j : n_j ≥ 2} d_j · (n_{Aj}/n_j) · (1 − n_{Aj}/n_j) · (n_j − d_j)/(n_j − 1)

De dónde sale: si, condicionado al conjunto de riesgo en τ_j, las d_j muertes
son un subconjunto uniforme de los n_j rasgos en riesgo, entonces
d_{Aj} ~ Hipergeométrica(n_j, n_{Aj}, d_j). Su media es d_j n_{Aj}/n_j y su
varianza es el término de arriba. El factor (n_j − d_j)/(n_j − 1) corrige los
empates y vale 1 si d_j = 1. Si n_j = 1, entonces d_j = 1 y el término es 0.

  κ = Var_perm(U) / V = n_A n_B Σ_k S_k² / (K(K − 1) · V)

### 4.2 Propiedades

- **(κ1) V depende de las etiquetas, Var_perm(U) no.** Por tanto κ se refiere
  a la asignación observada y cambia al permutar. Una versión que no depende
  de las etiquetas es κ̄ = Var_perm(U)/E_perm[V], con la media tomada sobre las
  mismas C(K, n_A) asignaciones.

- **(κ2) Si m_k = 1 para todo k, entonces Var_perm(U) = E_perm[V] de forma exacta.**
  Por tanto κ̄ = 1, y κ fluctúa alrededor de 1.

  *Demostración.* Con m_k = 1, A* es un subconjunto uniforme de rasgos de
  tamaño N_A. Sea F_j la información sobre las etiquetas de los rasgos que
  mueren en τ₁, …, τ_j. Sin censura, n_{Aj} = N_A − Σ_{l<j} d_{Al} es medible
  respecto de F_{j−1}. Condicionado a F_{j−1}, las etiquetas no reveladas de
  los n_j rasgos en riesgo forman un subconjunto uniforme de tamaño n_{Aj}.
  El conjunto de los que mueren en τ_j está fijado por los tiempos, así que
  d_{Aj} | F_{j−1} ~ Hipergeométrica(n_j, n_{Aj}, d_j). Los términos
  D_j = d_{Aj} − E[d_{Aj} | F_{j−1}] son diferencias de martingala, y por tanto
  incorreladas. Así, Var(U) = Σ_j E[D_j²] = E[Σ_j Var(d_{Aj} | F_{j−1})] = E[V]. ∎

  Comprobado de forma exacta en el apartado (d), con y sin empates. Ahí κ vale
  0.933 y 0.958.

- **(κ3) Calibración con m_k = m constante.** Sean Q = Σᵢ M̂ᵢ² y
  κ₀ = (N − 1) Σ_k S_k² / ((K − 1) m Q). Esta cantidad es exactamente
  Var_perm,diagramas(U) / E_perm,rasgos[V], donde el denominador sale de (κ2)
  aplicado a nivel de rasgo. Si los rasgos se reparten al azar entre los
  diagramas, es decir, si no hay dependencia dentro del diagrama, entonces
  E[κ₀] = 1.

  *Demostración.* Q no depende del reparto. S_k es el total de m valores
  tomados sin reemplazo de {M̂ᵢ}, cuya media es 0. Por tanto
  E[S_k²] = m(N − m)Q/(N(N − 1)), y sumando sobre k,
  E[Σ_k S_k²] = (N − m)Q/(N − 1) = m(K − 1)Q/(N − 1). Sustituyendo, E[κ₀] = 1. ∎

  κ₀ es, por tanto, un "efecto de diseño" en el sentido de Kish, del tipo
  1 + (m − 1)ρ. Comprobado de forma exacta en el apartado (i): la media sobre
  las 15 particiones es 1.

- **(κ4) Degeneración.** Si 0 < N_A < N, V = 0 si y solo si todos los tiempos
  coinciden. *Prueba:* en τ₁, n₁ = N y 0 < n_{A1} < N, así que el término es
  nulo solo si d₁ = N. En ese caso M̂ ≡ 0, Var(U) = 0 y κ = 0/0 (apartado (h)).
  Si en la asignación observada el grupo A tiene solo diagramas vacíos
  (N_A = 0), entonces V = 0 pero Var_perm(U) puede ser positiva, y κ = ∞.

### 4.3 Valores en los casos de prueba

| | V_obs | κ | E_perm[V] | κ̄ | p bilateral exacto |
|---|---|---|---|---|---|
| Caso 1 | 6.406922 | 1.874 | 5.810482 | 2.067 | 3/5 |
| Caso 2 | 3.262422 | 1.866 | 3.111527 | 1.957 | 23/35 |

Hay dependencia positiva dentro de cada diagrama (una escala común por
diagrama). Por eso la varianza clásica V subestima la varianza correcta por un
factor cercano a 2, y la log-rank clásica sería anticonservadora.

---

## 5. Qué es clásico y qué podría ser nuevo

**Clásico.** Solo cito referencias que conozco con seguridad.

- La log-rank y su varianza hipergeométrica: Mantel (1966), *Cancer
  Chemotherapy Reports* 50, 163–170; Mantel y Haenszel (1959), *JNCI* 22,
  719–748; Peto y Peto (1972), *JRSS A* 135, 185–207.
- Nelson–Aalen: Nelson (1972), *Technometrics* 14, 945–966; Aalen (1978),
  *Ann. Statist.* 6, 701–726.
- Residuos martingala δᵢ − Λ̂(tᵢ) y su suma nula: Therneau, Grambsch y Fleming
  (1990), *Biometrika* 77, 147–160; Therneau y Grambsch (2000), *Modeling
  Survival Data*, Springer.
- Log-rank = score de Cox en β = 0 con empates de Breslow. La forma
  U = Σᵢ Zᵢ M̂ᵢ sale directamente de la representación del score en procesos
  de conteo (Fleming y Harrington 1991; Andersen, Borgan, Gill y Keiding 1993).
  **El Lema 1 es este hecho, agrupando los rasgos por diagrama.**
- Sin censura, la log-rank es equivalente a la prueba de scores exponenciales
  de Savage (1956), *Ann. Math. Statist.* 27, 590–615.
- La varianza del total en muestreo sin reemplazo, con corrección por población
  finita, está en Cochran (1977), *Sampling Techniques*. Pruebas de
  permutación: Pitman (1937). TCL en poblaciones finitas: Hájek (1960).
  **El Lema 2 es esta fórmula aplicada a los S_k.**
- Var(U) = E[V] bajo permutación de rasgos (κ2) es una consecuencia estándar
  de la estructura de martingala. No tengo una cita precisa que pueda
  verificar aquí.
- Datos de supervivencia agrupados (clustered), relacionados con este caso:
  la varianza robusta de Lin y Wei (1989), *JASA* 84, 1074–1078, también suma
  cuadrados de contribuciones por conglomerado. No coincide con Σ S_k²,
  porque el score robusto centra con Z̄(t). Sé que hay literatura sobre pruebas
  de aleatorización por conglomerados (ensayos aleatorizados por
  conglomerados), pero no doy una cita concreta porque no puedo verificarla.

**Lo que podría ser nuevo.** No he podido comprobar el estado del arte.

- Aplicar la log-rank a persistencias de diagramas, tratando cada diagrama como
  un conglomerado y permutando diagramas, con la varianza en forma cerrada
  n_A n_B Σ S_k²/(K(K−1)).
- Usar κ como diagnóstico de la dependencia entre rasgos de un mismo diagrama
  en TDA.

Las dos propiedades de calibración (κ2 y κ3) son elementales. No sé si
aparecen en el artículo.

**Recomendación para el artículo.** Presentar los dos lemas como consecuencias
directas de resultados clásicos, con las citas de arriba, y no como resultados
nuevos. La aportación está en el uso: el diagrama como unidad de
intercambiabilidad.

---

## 6. Explicación en una llamada

**Lema 1 (ES).** A cada rasgo le corresponde un residuo: una muerte menos el
riesgo que el Nelson–Aalen conjunto acumuló hasta su muerte. Si sumas esos
residuos en el grupo A obtienes exactamente el numerador de la log-rank, porque
las dos cuentas usan los mismos conjuntos de riesgo. Sin censura, cada rasgo
muere una sola vez y el Nelson–Aalen reparte exactamente esas muertes, así que
todos los residuos juntos suman cero. Los empates no molestan siempre que el
salto sea d entre n.

**Lemma 1 (EN).** Each feature gets a residual: one death minus the hazard
the pooled Nelson–Aalen accumulated up to its death time. Summing those
residuals over group A gives exactly the log-rank numerator, because both
sides count the same risk sets. With no censoring, every feature dies exactly
once and Nelson–Aalen hands out exactly those deaths, so all the residuals add
up to zero. Ties are fine as long as each jump is d over n.

**Lema 2 (ES).** Si barajas qué diagramas son A y cuáles son B, la curva
Nelson–Aalen conjunta no cambia, así que cada diagrama conserva su total de
residuos. La log-rank pasa a ser la suma de n_A de esos totales sacados al azar
sin reemplazo, y su varianza es la fórmula de libro con corrección por
población finita. Como se barajan diagramas enteros, se respeta la dependencia
entre rasgos del mismo diagrama, que es justo lo que ignora la varianza
clásica. Con pocos diagramas la fórmula sigue siendo exacta, pero hay muy pocos
p-valores posibles.

**Lemma 2 (EN).** If you shuffle which diagrams are A and which are B, the
pooled Nelson–Aalen curve doesn't change, so each diagram keeps its residual
total. The log-rank numerator becomes the sum of n_A of those totals drawn at
random without replacement, and its variance is the textbook finite-population
formula. Because whole diagrams are shuffled, the dependence between features
of the same diagram is respected, which is exactly what the classical variance
ignores. With few diagrams the formula is still exact, but there are only a
handful of attainable p-values.

---

## 7. Veredicto global

| | Veredicto | Condiciones que no se pueden quitar |
|---|---|---|
| Lema 1 | **Correcto** | Incremento d_j/n_j, Λ̂ continuo por la derecha, n_j con ≥, sin censura (o residuos δ − Λ̂). La prueba propuesta necesita la versión restringida a A |
| Lema 2 | **Correcto** | Permutación uniforme de diagramas con n_A fijo y K ≥ 2. Para que la prueba sea exacta, intercambiabilidad de diagramas bajo H0 |
| V y κ | Bien definidos si V > 0 | κ depende de la asignación observada. κ̄ o κ₀ están mejor calibrados (κ2, κ3) |
