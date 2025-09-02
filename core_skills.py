import random

rand_list = [random.randint(1, 20) for _ in range(10)]

list_comprehension_below_10 = [x for x in rand_list if x < 10]

list_comprehension_below_10 = filter(lambda x: x if x < 10 else False, rand_list)
