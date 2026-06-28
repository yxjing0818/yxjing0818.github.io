---
title: 点到曲线投影：Point Inversion 的算法设计与退化处理
date: 2026-06-28
tags: [几何, 算法, 数值计算]
summary: 从最近距离的一阶条件出发，整理 point inversion 的 Newton 迭代、初值选择、fallback、边界处理和多解策略。
---

点到曲线投影，也常被称为 **point inversion**，是几何建模、CAD、曲线编辑、碰撞检测和最近点查询中非常基础的问题。

问题可以描述为：

给定一个空间点 `P` 和一条参数曲线 `C(u)`，在曲线上找到距离 `P` 最近的点。

数学形式是：

$$
u^\ast = \operatorname*{arg\,min}_{u \in [u_{\min}, u_{\max}]} \lVert C(u)-P \rVert
$$

其中 `u` 是曲线参数，`C(u*)` 就是点 `P` 在曲线上的最近投影点。

这个问题看起来简单，但要写出稳定的工程实现并不只是套一个 Newton 迭代。真实场景里会遇到初值不好、曲线端点、闭合曲线、局部极值、多解、导数退化、迭代发散等问题。本文系统整理一种常用的稳健求解思路。

## 1. 从最近距离到目标函数

最近点问题本质上是在最小化距离：

$$
D(u)=\lVert C(u)-P \rVert
$$

实际计算中通常改为最小化平方距离，避免频繁开方：

$$
F(u)=\frac{1}{2}\lVert C(u)-P \rVert^2
$$

设：

$$
r(u)=C(u)-P
$$

则：

$$
F(u)=\frac{1}{2}r(u)\cdot r(u)
$$

如果最近点落在曲线参数区间内部，那么它应满足一阶必要条件：

$$
F'(u)=0
$$

对 `F(u)` 求导：

$$
F'(u)=r(u)\cdot C'(u)
$$

于是得到 point inversion 的核心方程：

$$
f(u)=(C(u)-P)\cdot C'(u)=0
$$

几何意义是：在最近点处，曲线点 `C(u)` 与外部点 `P` 之间的连线，应该垂直于曲线切线 `C'(u)`。

## 2. Newton-Raphson 求解

要解的是：

$$
f(u)=0
$$

其中：

$$
f(u)=(C(u)-P)\cdot C'(u)
$$

Newton-Raphson 需要 `f'(u)`。

继续对 `f(u)` 求导：

$$
f'(u)=C'(u)\cdot C'(u)+(C(u)-P)\cdot C''(u)
$$

也就是：

$$
f'(u)=\lVert C'(u)\rVert^2+(C(u)-P)\cdot C''(u)
$$

Newton 更新公式为：

$$
u_{\text{next}}=u-\frac{f(u)}{f'(u)}
$$

完整写开：

$$
u_{\text{next}}
= u-\frac{(C(u)-P)\cdot C'(u)}{\lVert C'(u)\rVert^2+(C(u)-P)\cdot C''(u)}
$$

如果初值接近正确解，并且曲线在该区域不退化，Newton 通常收敛很快。

但 Newton 是局部方法，不保证全局最优，也不保证一定收敛。因此，一个可靠的点到曲线投影算法，必须把 Newton 放在一套更完整的策略里。

## 3. 初值选择：先粗定位

Newton 对初值非常敏感。初值差一点，可能收敛到错误局部解；初值差很多，可能直接发散。

一个实用的初值策略是：

```text
先粗采样找近似位置，再用 Newton 精化
```

### 3.1 使用控制多边形粗定位

对于 Bezier、B 样条、NURBS 等曲线，控制多边形通常能粗略反映曲线形状。

可以先把点 `P` 投影到控制多边形的每一条线段上。

对线段 `A -> B`：

$$
\begin{aligned}
AB &= B-A \\
t &= \frac{(P-A)\cdot AB}{AB\cdot AB} \\
t &= \operatorname{clamp}(t,0,1) \\
Q &= A+t\,AB
\end{aligned}
$$

`Q` 是 `P` 在线段 `AB` 上的最近点。

遍历所有控制多边形线段，找到距离 `P` 最近的线段位置，再把这个位置映射到曲线参数域：

$$
\begin{aligned}
\alpha &= \frac{\mathrm{segment\_index}+t}{\mathrm{segment\_count}} \\
u_0 &= u_{\min}+\alpha\,(u_{\max}-u_{\min})
\end{aligned}
$$

这种方法非常方便，适合快速获得一个大致初值。

不过它只是近似。控制多边形的参数分布不等同于曲线真实参数分布，所以还需要进一步校正。

### 3.2 对真实曲线做粗采样

更直接的办法是在曲线参数域上均匀采样：

```text
for k = 0..N:
    u = u_min + (u_max - u_min) * k / N
    d2 = ||C(u) - P||^2
    记录 d2 最小的 u
```

建议采样数量：

$$
N=\max(64,\;32\times \mathrm{control\_point\_count})
$$

这一步比控制多边形稍复杂，但它评估的是真实曲线，因此更可靠。

实践中常用组合策略：

```text
控制多边形粗定位
-> 曲线粗采样校正
-> 取最小距离候选作为 Newton 初值
```

## 4. 细采样与 fallback 方法选择

Newton 快，但不总是稳。需要准备不依赖导数的 fallback。

常见 fallback 可以分为四类。

### 4.1 均匀细采样

最简单的方法是把参数区间分成很多小段，直接取距离最小的采样点。

优点：

- 实现简单。
- 不依赖导数。
- 很适合调试或生成参考试验。

缺点：

- 精度依赖采样数量。
- 想要高精度就必须采很多点。
- 对长曲线或大量查询不够高效。

均匀细采样适合作为最基础的保险策略，但不是性能最优方案。

### 4.2 区间二分细分

更稳健的方案是对参数区间递归二分：

$$
[u_{\min},u_{\max}]\rightarrow [u_{\min},u_{\mathrm{mid}}]\cup [u_{\mathrm{mid}},u_{\max}]
$$

每个区间估计一个空间包围盒。点 `P` 到这个包围盒的最小距离，可以作为该区间内曲线距离的下界。

如果某个区间的下界已经大于当前最优距离，就可以剪枝：

```text
if lower_bound_distance > best_distance:
    discard interval
```

这种方法可以避免盲目搜索所有区域。

### 4.3 bounding box 二分细分

对于一般参数曲线，可以在每个参数子区间内采几个点来估算局部 bounding box：

```text
u0 = lo
u1 = (lo + mid) / 2
u2 = mid
u3 = (mid + hi) / 2
u4 = hi
```

用这些点形成一个近似包围盒，再计算点 `P` 到包围盒的最小距离。

严格来说，这种采样包围盒不是数学上的严格包围盒，因为曲线可能在采样点之间超出盒子。更严格的做法是利用 Bezier/B-spline 的 convex hull 性质，在子区间上做 subdivision 后用控制点包围盒。  

工程上，如果目标是 fallback 兜底而不是形式化证明，采样 bounding box 往往已经足够实用。

### 4.4 黄金分割细化

当 fallback 已经找到一个较小候选区间后，可以用黄金分割搜索继续细化最小距离点。

设当前区间为 `[lo, hi]`：

$$
\begin{aligned}
\varphi &= \frac{\sqrt{5}-1}{2} \\
x_1 &= hi-\varphi(hi-lo) \\
x_2 &= lo+\varphi(hi-lo)
\end{aligned}
$$

比较：

$$
\lVert C(x_1)-P\rVert^2
\quad\text{and}\quad
\lVert C(x_2)-P\rVert^2
$$

不断缩小区间。

黄金分割不需要导数，适合在局部区间内稳定细化。

推荐组合：

```text
Newton 正常收敛：直接返回
Newton 失败：bounding box 二分细分
找到候选区间后：黄金分割细化
```

## 5. 迭代步长过小时的早停

Newton 每次迭代会产生一个参数更新量：

$$
\delta=\frac{f(u)}{f'(u)}
$$

如果：

$$
|\delta|<\mathrm{tol}_{\mathrm{parameter}}
$$

说明参数已经几乎不再变化，可以认为迭代收敛。

建议默认值：

$$
\mathrm{tol}_{\mathrm{parameter}}=10^{-6}
$$

早停时仍然应该重新计算距离：

$$
\mathrm{distance}=\lVert C(u)-P\rVert
$$

因为最后返回的不只是参数 `u`，还包括投影距离。

还可以使用距离早停：

$$
\lVert C(u)-P\rVert < \mathrm{tol}_{\mathrm{distance}}
$$

建议默认值：

$$
\mathrm{tol}_{\mathrm{distance}}=10^{-9}
$$

当点本身就在曲线上时，距离早停非常有效。

## 6. 迭代发散时的处理

Newton 发散或不可靠的常见信号包括：

- `|f(u)|` 没有下降。
- `|f(u)|` 连续多次不下降。
- `f'(u)` 接近 0。
- 参数在边界附近来回跳动。
- 更新步长突然变得很大。

一个简单实用的发散检测规则是：

如果 $|f|$ 连续 3 次不下降，则认为 Newton 不可靠。

同时建议加入导数退化判断：

$$
|f'(u)| < \varepsilon
$$

其中 `epsilon` 可以取类似：

$$
10^{-14}
$$

一旦判定 Newton 不可靠，就不要继续硬迭代，而是进入 fallback：

改为直接最小化 $\lVert C(u)-P\rVert^2$。

这个 fallback 可以是均匀细采样，也可以是 bounding box 二分细分加黄金分割。

## 7. 参数越界时的处理

Newton 更新可能让参数跑出定义域：

$$
u_{\text{next}}<u_{\min}
$$

或：

$$
u_{\text{next}}>u_{\max}
$$

这时要看曲线是开曲线还是闭曲线。

### 7.1 开曲线：clamp

开曲线的参数域是一个普通闭区间：

$$
[u_{\min},u_{\max}]
$$

如果 `u` 越界，应该夹回参数域：

$$
u=\operatorname{clamp}(u,u_{\min},u_{\max})
$$

原因是开曲线的最近点可能就是端点。端点解不一定满足内部垂直条件：

$$
(C(u)-P)\cdot C'(u)=0
$$

因此，开曲线最终还应该显式比较端点距离：

$$
\begin{aligned}
d_{\mathrm{left}} &= \lVert C(u_{\min})-P\rVert \\
d_{\mathrm{right}} &= \lVert C(u_{\max})-P\rVert
\end{aligned}
$$

如果端点更近，应直接返回端点参数。

### 7.2 闭曲线：wrap

闭曲线没有真正的起点和终点。如果：

$$
C(u_{\min})\approx C(u_{\max})
$$

就可以把参数当成周期变量处理。

越界时做周期回绕：

$$
\begin{aligned}
\mathrm{period} &= u_{\max}-u_{\min} \\
u &= u_{\min}+\operatorname{mod}(u-u_{\min},\mathrm{period})
\end{aligned}
$$

如果 `mod` 结果为负，则加一个周期。

闭曲线不建议 clamp。clamp 会人为制造边界，导致投影点在参数端点附近不连续。

## 8. 等距多解时的策略

点到曲线投影可能存在多个全局最近点。

例如一条对称曲线和一个位于对称轴上的点，左右两侧可能同样近。此时最近点不是唯一的。

如果算法没有明确 tie-break 策略，结果可能受以下因素影响：

- 采样顺序。
- 浮点误差。
- 初值选择。
- 编译器优化。
- 曲线参数化方式。

常见处理策略有几种。

### 8.1 返回最小参数

如果多个解距离相同，返回最小的 `u`。

优点是确定性强，适合测试和批处理。

缺点是它只是算法约定，不一定符合交互语义。

### 8.2 返回最大参数

与返回最小参数类似，只是偏向参数更大的一侧。

适合某些有方向性的曲线处理流程。

### 8.3 返回离初值最近的解

如果调用方有上一帧参数或用户指定的初值，可以选离该初值最近的解：

$$
\min |u-u_{\mathrm{initial}}|
$$

这种方式适合交互场景，比如拖拽曲线上的投影点。它可以减少投影点在多个等距解之间突然跳变。

### 8.4 返回所有候选解

更完整的接口可以返回所有近似等距的候选：

```text
[{u1, distance}, {u2, distance}, ...]
```

调用方再根据业务规则选择。

优点是信息完整。

缺点是接口复杂度更高，调用方也必须理解多解问题。

### 8.5 推荐策略

如果是底层几何库，建议支持两级设计：

```text
默认接口：返回一个确定性解
高级接口：可返回多个候选解
```

默认 tie-break 可以选择：

```text
距离相同时返回最小参数
```

交互应用则更推荐：

```text
距离相同时返回离上一帧参数最近的解
```

## 9. 迭代次数不够时怎么办

Newton 需要最大迭代次数限制：

$$
\mathrm{max\_iter}
$$

建议默认值：

$$
\mathrm{max\_iter}=50
$$

绝大多数正常情况用不到 50 次。但最大次数可以避免极端输入导致死循环。

当达到 `max_iter` 仍未收敛时，有两种常见策略。

### 9.1 返回未收敛

直接返回：

```text
converged = false
```

同时附带当前最好的：

```text
u
distance
iterations
```

这种方式比较诚实，适合调用方希望自己接管失败处理的场景。

### 9.2 自动进入 fallback

另一种方式是：

```text
Newton 未收敛
-> 进入不依赖导数的 fallback
-> 尽量返回可用结果
```

这种方式对调用方更友好，尤其适合应用层。

推荐做法是把策略暴露为选项：

```text
on_max_iter = return_failure
on_max_iter = fallback
```

如果只提供一个默认行为，通常建议选择 fallback，因为最近点查询大多希望“尽量给出答案”。

## 10. 容差参数建议

一个常用默认配置是：

$$
\begin{aligned}
\mathrm{tol}_{\mathrm{distance}} &= 10^{-9} \\
\mathrm{tol}_{\mathrm{parameter}} &= 10^{-6} \\
\mathrm{max\_iter} &= 50
\end{aligned}
$$

它们分别控制：

- `tol_distance`：空间距离收敛阈值。
- `tol_parameter`：参数变化收敛阈值。
- `max_iter`：Newton 最大迭代次数。

需要注意，`tol_distance` 最好和模型尺度相关。

如果模型尺寸约为 `model_size`，可以考虑：

$$
\mathrm{tol}_{\mathrm{distance}}=\mathrm{model\_size}\times 10^{-9}
$$

固定使用 `1e-9` 在非常大或非常小的模型上都可能不合适。

## 11. 推荐算法流程

一个稳健的 point inversion 可以按下面流程实现：

```text
输入：
    点 P
    参数曲线 C(u)
    参数域 [u_min, u_max]
    容差 tol_distance, tol_parameter
    最大迭代次数 max_iter

流程：
    1. 判断曲线是开曲线还是闭曲线
    2. 用控制多边形或低成本代理几何选择初值
    3. 对真实曲线做粗采样，修正初值
    4. 进入 Newton 迭代
    5. 每轮计算 f(u) 和 f'(u)
    6. 如果 f'(u) 退化，进入 fallback
    7. 更新 u_next = u - f/f'
    8. 开曲线 clamp，闭曲线 wrap
    9. 如果 |delta| < tol_parameter，早停
    10. 如果 distance < tol_distance，早停
    11. 如果 |f| 连续 3 次不下降，进入 fallback
    12. 如果超过 max_iter，按策略失败返回或 fallback
    13. 对开曲线显式比较端点距离
    14. 对多解情况应用 tie-break 策略
    15. 返回 u、投影点 C(u)、距离、收敛状态和迭代次数
```

## 12. 伪代码

```text
function project_point_to_curve(P, curve):
    [u_min, u_max] = curve.parameter_domain

    if curve.is_closed():
        boundary_policy = wrap
    else:
        boundary_policy = clamp

    u = choose_initial_guess(P, curve)
    previous_abs_f = infinity
    non_decrease_count = 0

    for iter in 1..max_iter:
        C   = curve.position(u)
        Cp  = curve.first_derivative(u)
        Cpp = curve.second_derivative(u)

        f  = dot(C - P, Cp)
        df = dot(Cp, Cp) + dot(C - P, Cpp)

        if abs(df) < derivative_epsilon:
            return fallback_minimize_distance(P, curve)

        abs_f = abs(f)
        if abs_f >= previous_abs_f:
            non_decrease_count += 1
        else:
            non_decrease_count = 0
        previous_abs_f = abs_f

        if non_decrease_count >= 3:
            return fallback_minimize_distance(P, curve)

        delta = f / df
        u = boundary_policy(u - delta)

        if abs(delta) < tol_parameter:
            return make_result(u)

        if distance(curve.position(u), P) < tol_distance:
            return make_result(u)

    if max_iter_policy == fallback:
        return fallback_minimize_distance(P, curve)
    else:
        return make_unconverged_result(u)
```

## 13. 工程结论

点到曲线投影的核心公式很短：

$$
(C(u)-P)\cdot C'(u)=0
$$

但真正可靠的实现，需要围绕它建立完整的数值保护：

- 粗采样解决初值问题。
- Newton 负责快速精化。
- 参数早停避免无意义迭代。
- 发散检测避免错误收敛。
- fallback 保证极端输入下仍有答案。
- 开曲线 clamp，闭曲线 wrap。
- 端点显式比较。
- 多解时定义稳定策略。
- 迭代不足时明确失败或兜底。

一句话总结：

```text
Newton 让算法快，采样和细分让算法稳，清晰的边界策略让结果可预测。
```
