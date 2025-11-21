# Copyright (c) Microsoft Corporation. 
# Licensed under the MIT license.

# from tree_sitter import Language, Parser
# from .utils import (remove_comments_and_docstrings,
#                    tree_to_token_index,
#                    index_to_code_token,
#                    tree_to_variable_index)

# import re
# from io import StringIO
# import tokenize


def tree_to_token_index(root_node):
    if (len(root_node.children) == 0 or root_node.type == 'string') and root_node.type != 'comment':
        return [(root_node.start_point, root_node.end_point)]
    else:
        code_tokens = []
        for child in root_node.children:
            code_tokens += tree_to_token_index(child)
        return code_tokens


def tree_to_variable_index(root_node, point2code):
    if (len(root_node.children) == 0 or root_node.type == 'string') and root_node.type != 'comment':
        index = (root_node.start_point, root_node.end_point)
        _, code = point2code[index]
        if root_node.type != code:
            return [(root_node.start_point, root_node.end_point)]
        else:
            return []
    else:
        code_tokens = []
        for child in root_node.children:
            code_tokens += tree_to_variable_index(child, point2code)
        return code_tokens


def index_to_code_token(index, code):
    start_point = index[0]
    end_point = index[1]
    if start_point[0] == end_point[0]:
        s = code[start_point[0]][start_point[1]:end_point[1]]
    else:
        s = ""
        s += code[start_point[0]][start_point[1]:]
        for i in range(start_point[0] + 1, end_point[0]):
            s += code[i]
        s += code[end_point[0]][:end_point[1]]
    return s


def DFG_python(root_node,point2code,states):
    assignment=['assignment','augmented_assignment','for_in_clause']
    if_statement=['if_statement']
    for_statement=['for_statement']
    while_statement=['while_statement']
    do_first_statement=['for_in_clause'] 
    def_statement=['default_parameter']
    states=states.copy() 
    if (len(root_node.children)==0 or root_node.type=='string') and root_node.type!='comment':        
        idx,code=point2code[(root_node.start_point,root_node.end_point)]
        if root_node.type==code:
            return [],states
        elif code in states:
            return [(code,idx,'comesFrom',[code],states[code].copy())],states
        else:
            if root_node.type=='identifier':
                states[code]=[idx]
            return [(code,idx,'comesFrom',[],[])],states
    elif root_node.type in def_statement:
        name=root_node.child_by_field_name('name')
        value=root_node.child_by_field_name('value')
        DFG=[]
        if value is None:
            indexs=tree_to_variable_index(name,point2code)
            for index in indexs:
                idx,code=point2code[index]
                DFG.append((code,idx,'comesFrom',[],[]))
                states[code]=[idx]
            return sorted(DFG,key=lambda x:x[1]),states
        else:
            name_indexs=tree_to_variable_index(name,point2code)
            value_indexs=tree_to_variable_index(value,point2code)
            temp,states=DFG_python(value,point2code,states)
            DFG+=temp
            for index1 in name_indexs:
                idx1,code1=point2code[index1]
                for index2 in value_indexs:
                    idx2,code2=point2code[index2]
                    DFG.append((code1,idx1,'comesFrom',[code2],[idx2]))
                states[code1]=[idx1]
            return sorted(DFG,key=lambda x:x[1]),states
    elif root_node.type in assignment:
        if root_node.type=='for_in_clause':
            right_nodes=[root_node.children[-1]]
            left_nodes=[root_node.child_by_field_name('left')]
        else:
            if root_node.child_by_field_name('right') is None:
                return [],states
            left_nodes=[x for x in root_node.child_by_field_name('left').children if x.type!=',']
            right_nodes=[x for x in root_node.child_by_field_name('right').children if x.type!=',']
            if len(right_nodes)!=len(left_nodes):
                left_nodes=[root_node.child_by_field_name('left')]
                right_nodes=[root_node.child_by_field_name('right')]
            if len(left_nodes)==0:
                left_nodes=[root_node.child_by_field_name('left')]
            if len(right_nodes)==0:
                right_nodes=[root_node.child_by_field_name('right')]
        DFG=[]
        for node in right_nodes:
            temp,states=DFG_python(node,point2code,states)
            DFG+=temp

        for left_node,right_node in zip(left_nodes,right_nodes):
            left_tokens_index=tree_to_variable_index(left_node,point2code)
            right_tokens_index=tree_to_variable_index(right_node,point2code)
            temp=[]
            for token1_index in left_tokens_index:
                idx1,code1=point2code[token1_index]
                temp.append((code1,idx1,'computedFrom',[point2code[x][1] for x in right_tokens_index],
                             [point2code[x][0] for x in right_tokens_index]))
                states[code1]=[idx1]
            DFG+=temp
        return sorted(DFG,key=lambda x:x[1]),states
    elif root_node.type in if_statement:
        DFG=[]
        current_states=states.copy()
        others_states=[]
        tag=False
        if 'else' in root_node.type:
            tag=True
        for child in root_node.children:
            if 'else' in child.type:
                tag=True
            if child.type not in ['elif_clause','else_clause']:
                temp,current_states=DFG_python(child,point2code,current_states)
                DFG+=temp
            else:
                temp,new_states=DFG_python(child,point2code,states)
                DFG+=temp
                others_states.append(new_states)
        others_states.append(current_states)
        if tag is False:
            others_states.append(states)
        new_states={}
        for dic in others_states:
            for key in dic:
                if key not in new_states:
                    new_states[key]=dic[key].copy()
                else:
                    new_states[key]+=dic[key]
        for key in new_states:
            new_states[key]=sorted(list(set(new_states[key])))
        return sorted(DFG,key=lambda x:x[1]),new_states
    elif root_node.type in for_statement:
        DFG=[]
        for i in range(2):
            right_nodes=[x for x in root_node.child_by_field_name('right').children if x.type!=',']
            left_nodes=[x for x in root_node.child_by_field_name('left').children if x.type!=',']
            if len(right_nodes)!=len(left_nodes):
                left_nodes=[root_node.child_by_field_name('left')]
                right_nodes=[root_node.child_by_field_name('right')]
            if len(left_nodes)==0:
                left_nodes=[root_node.child_by_field_name('left')]
            if len(right_nodes)==0:
                right_nodes=[root_node.child_by_field_name('right')]
            for node in right_nodes:
                temp,states=DFG_python(node,point2code,states)
                DFG+=temp
            for left_node,right_node in zip(left_nodes,right_nodes):
                left_tokens_index=tree_to_variable_index(left_node,point2code)
                right_tokens_index=tree_to_variable_index(right_node,point2code)
                temp=[]
                for token1_index in left_tokens_index:
                    idx1,code1=point2code[token1_index]
                    temp.append((code1,idx1,'computedFrom',[point2code[x][1] for x in right_tokens_index],
                                 [point2code[x][0] for x in right_tokens_index]))
                    states[code1]=[idx1]
                DFG+=temp
            if  root_node.children[-1].type=="block":
                temp,states=DFG_python(root_node.children[-1],point2code,states)
                DFG+=temp
        dic={}
        for x in DFG:
            if (x[0],x[1],x[2]) not in dic:
                dic[(x[0],x[1],x[2])]=[x[3],x[4]]
            else:
                dic[(x[0],x[1],x[2])][0]=list(set(dic[(x[0],x[1],x[2])][0]+x[3]))
                dic[(x[0],x[1],x[2])][1]=sorted(list(set(dic[(x[0],x[1],x[2])][1]+x[4])))
        DFG=[(x[0],x[1],x[2],y[0],y[1]) for x,y in sorted(dic.items(),key=lambda t:t[0][1])]
        return sorted(DFG,key=lambda x:x[1]),states
    elif root_node.type in while_statement:
        DFG=[]
        for i in range(2):
            for child in root_node.children:
                temp,states=DFG_python(child,point2code,states)
                DFG+=temp
        dic={}
        for x in DFG:
            if (x[0],x[1],x[2]) not in dic:
                dic[(x[0],x[1],x[2])]=[x[3],x[4]]
            else:
                dic[(x[0],x[1],x[2])][0]=list(set(dic[(x[0],x[1],x[2])][0]+x[3]))
                dic[(x[0],x[1],x[2])][1]=sorted(list(set(dic[(x[0],x[1],x[2])][1]+x[4])))
        DFG=[(x[0],x[1],x[2],y[0],y[1]) for x,y in sorted(dic.items(),key=lambda t:t[0][1])]
        return sorted(DFG,key=lambda x:x[1]),states
    else:
        DFG=[]
        for child in root_node.children:
            if child.type in do_first_statement:
                temp,states=DFG_python(child,point2code,states)
                DFG+=temp
        for child in root_node.children:
            if child.type not in do_first_statement:
                temp,states=DFG_python(child,point2code,states)
                DFG+=temp

        return sorted(DFG,key=lambda x:x[1]),states

def DFG_java(root_node,point2code,states):
    assignment=['assignment_expression']
    def_statement=['variable_declarator']
    increment_statement=['update_expression']
    if_statement=['if_statement','else']
    for_statement=['for_statement']
    enhanced_for_statement=['enhanced_for_statement']
    while_statement=['while_statement']
    do_first_statement=[]
    states=states.copy()
    if (len(root_node.children)==0 or root_node.type=='string') and root_node.type!='line_comment': #java代码中是line_comment
        idx,code=point2code[(root_node.start_point,root_node.end_point)]
        if root_node.type==code:
            return [],states
        elif code in states:
            return [(code,idx,'comesFrom',[code],states[code].copy())],states
        else:
            if root_node.type=='identifier':
                states[code]=[idx]
            return [(code,idx,'comesFrom',[],[])],states
    elif root_node.type in def_statement:
        name=root_node.child_by_field_name('name')
        value=root_node.child_by_field_name('value')
        DFG=[]
        if value is None:
            indexs=tree_to_variable_index(name,point2code)
            for index in indexs:
                idx,code=point2code[index]
                DFG.append((code,idx,'comesFrom',[],[]))
                states[code]=[idx]
            return sorted(DFG,key=lambda x:x[1]),states
        else:
            name_indexs=tree_to_variable_index(name,point2code)
            value_indexs=tree_to_variable_index(value,point2code)
            temp,states=DFG_java(value,point2code,states)
            DFG+=temp
            for index1 in name_indexs:
                idx1,code1=point2code[index1]
                for index2 in value_indexs:
                    idx2,code2=point2code[index2]
                    DFG.append((code1,idx1,'comesFrom',[code2],[idx2]))
                states[code1]=[idx1]
            return sorted(DFG,key=lambda x:x[1]),states
    elif root_node.type in assignment:
        left_nodes=root_node.child_by_field_name('left')
        right_nodes=root_node.child_by_field_name('right')
        DFG=[]
        temp,states=DFG_java(right_nodes,point2code,states)
        DFG+=temp
        name_indexs=tree_to_variable_index(left_nodes,point2code)
        value_indexs=tree_to_variable_index(right_nodes,point2code)
        for index1 in name_indexs:
            idx1,code1=point2code[index1]
            for index2 in value_indexs:
                idx2,code2=point2code[index2]
                DFG.append((code1,idx1,'computedFrom',[code2],[idx2]))
            states[code1]=[idx1]
        return sorted(DFG,key=lambda x:x[1]),states
    elif root_node.type in increment_statement:
        DFG=[]
        indexs=tree_to_variable_index(root_node,point2code)
        for index1 in indexs:
            idx1,code1=point2code[index1]
            for index2 in indexs:
                idx2,code2=point2code[index2]
                DFG.append((code1,idx1,'computedFrom',[code2],[idx2]))
            states[code1]=[idx1]
        return sorted(DFG,key=lambda x:x[1]),states
    elif root_node.type in if_statement:
        DFG=[]
        current_states=states.copy()
        others_states=[]
        flag=False
        tag=False
        if 'else' in root_node.type:
            tag=True
        for child in root_node.children:
            if 'else' in child.type:
                tag=True
            if child.type not in if_statement and flag is False:
                temp,current_states=DFG_java(child,point2code,current_states)
                DFG+=temp
            else:
                flag=True
                temp,new_states=DFG_java(child,point2code,states)
                DFG+=temp
                others_states.append(new_states)
        others_states.append(current_states)
        if tag is False:
            others_states.append(states)
        new_states={}
        for dic in others_states:
            for key in dic:
                if key not in new_states:
                    new_states[key]=dic[key].copy()
                else:
                    new_states[key]+=dic[key]
        for key in new_states:
            new_states[key]=sorted(list(set(new_states[key])))
        return sorted(DFG,key=lambda x:x[1]),new_states
    elif root_node.type in for_statement:
        DFG=[]
        for child in root_node.children:
            temp,states=DFG_java(child,point2code,states)
            DFG+=temp
        flag=False
        for child in root_node.children:
            if flag:
                temp,states=DFG_java(child,point2code,states)
                DFG+=temp
            elif child.type=="local_variable_declaration":
                flag=True
        dic={}
        for x in DFG:
            if (x[0],x[1],x[2]) not in dic:
                dic[(x[0],x[1],x[2])]=[x[3],x[4]]
            else:
                dic[(x[0],x[1],x[2])][0]=list(set(dic[(x[0],x[1],x[2])][0]+x[3]))
                dic[(x[0],x[1],x[2])][1]=sorted(list(set(dic[(x[0],x[1],x[2])][1]+x[4])))
        DFG=[(x[0],x[1],x[2],y[0],y[1]) for x,y in sorted(dic.items(),key=lambda t:t[0][1])]
        return sorted(DFG,key=lambda x:x[1]),states
    elif root_node.type in enhanced_for_statement:
        name=root_node.child_by_field_name('name')
        value=root_node.child_by_field_name('value')
        body=root_node.child_by_field_name('body')
        DFG=[]
        for i in range(2):
            temp,states=DFG_java(value,point2code,states)
            DFG+=temp
            name_indexs=tree_to_variable_index(name,point2code)
            value_indexs=tree_to_variable_index(value,point2code)
            for index1 in name_indexs:
                idx1,code1=point2code[index1]
                for index2 in value_indexs:
                    idx2,code2=point2code[index2]
                    DFG.append((code1,idx1,'computedFrom',[code2],[idx2]))
                states[code1]=[idx1]
            temp,states=DFG_java(body,point2code,states)
            DFG+=temp
        dic={}
        for x in DFG:
            if (x[0],x[1],x[2]) not in dic:
                dic[(x[0],x[1],x[2])]=[x[3],x[4]]
            else:
                dic[(x[0],x[1],x[2])][0]=list(set(dic[(x[0],x[1],x[2])][0]+x[3]))
                dic[(x[0],x[1],x[2])][1]=sorted(list(set(dic[(x[0],x[1],x[2])][1]+x[4])))
        DFG=[(x[0],x[1],x[2],y[0],y[1]) for x,y in sorted(dic.items(),key=lambda t:t[0][1])]
        return sorted(DFG,key=lambda x:x[1]),states
    elif root_node.type in while_statement:
        DFG=[]
        for i in range(2):
            for child in root_node.children:
                temp,states=DFG_java(child,point2code,states)
                DFG+=temp
        dic={}
        for x in DFG:
            if (x[0],x[1],x[2]) not in dic:
                dic[(x[0],x[1],x[2])]=[x[3],x[4]]
            else:
                dic[(x[0],x[1],x[2])][0]=list(set(dic[(x[0],x[1],x[2])][0]+x[3]))
                dic[(x[0],x[1],x[2])][1]=sorted(list(set(dic[(x[0],x[1],x[2])][1]+x[4])))
        DFG=[(x[0],x[1],x[2],y[0],y[1]) for x,y in sorted(dic.items(),key=lambda t:t[0][1])]
        return sorted(DFG,key=lambda x:x[1]),states
    else:
        DFG=[]
        for child in root_node.children:
            if child.type in do_first_statement:
                temp,states=DFG_java(child,point2code,states)
                DFG+=temp
        for child in root_node.children:
            if child.type not in do_first_statement:
                temp,states=DFG_java(child,point2code,states)
                DFG+=temp

        return sorted(DFG,key=lambda x:x[1]),states
    

def CFG_java(root_node, point2code, entry_nodes=None):
    """
    为Java代码生成控制流图
    返回格式: (CFG, exit_nodes)
    CFG: 控制流边的列表，格式为 (from_code, from_idx, edge_type, to_code, to_idx)
    exit_nodes: 当前代码块的出口节点列表 [(code, idx), ...]
    entry_nodes: 当前代码块的入口节点列表 [(code, idx), ...]
    """
    assignment = ['assignment_expression']
    def_statement = ['variable_declarator', 'local_variable_declaration']
    increment_statement = ['update_expression']
    if_statement = ['if_statement']
    for_statement = ['for_statement']
    enhanced_for_statement = ['enhanced_for_statement']
    while_statement = ['while_statement']
    do_while_statement = ['do_statement']
    break_statement = ['break_statement']
    continue_statement = ['continue_statement']
    return_statement = ['return_statement']
    expression_statement = ['expression_statement']
    block_statement = ['block']
    
    if entry_nodes is None:
        entry_nodes = []
    
    # 处理叶节点或简单语句
    if (len(root_node.children) == 0 or root_node.type == 'string') and root_node.type != 'line_comment':
        if (root_node.start_point, root_node.end_point) in point2code:
            idx, code = point2code[(root_node.start_point, root_node.end_point)]
            current_node = (code, idx)
            
            # 创建从入口节点到当前节点的边
            CFG = []
            for entry_code, entry_idx in entry_nodes:
                CFG.append((entry_code, entry_idx, 'next', code, idx))
            
            return CFG, [current_node]
        else:
            return [], entry_nodes
    
    # 处理变量声明语句
    elif root_node.type in def_statement:
        CFG = []
        current_nodes = []
        
        # 获取声明语句的位置
        if (root_node.start_point, root_node.end_point) in point2code:
            idx, code = point2code[(root_node.start_point, root_node.end_point)]
            current_node = (code, idx)
            current_nodes = [current_node]
            
            # 从入口连接到当前语句
            for entry_code, entry_idx in entry_nodes:
                CFG.append((entry_code, entry_idx, 'next', code, idx))
        
        # 处理初始化表达式
        value = root_node.child_by_field_name('value')
        if value is not None:
            value_cfg, value_exits = CFG_java(value, point2code, current_nodes)
            CFG.extend(value_cfg)
            current_nodes = value_exits
        
        return CFG, current_nodes if current_nodes else entry_nodes
    
    # 处理赋值语句
    elif root_node.type in assignment:
        CFG = []
        
        # 获取赋值语句的位置
        if (root_node.start_point, root_node.end_point) in point2code:
            idx, code = point2code[(root_node.start_point, root_node.end_point)]
            current_node = (code, idx)
            
            # 从入口连接到赋值语句
            for entry_code, entry_idx in entry_nodes:
                CFG.append((entry_code, entry_idx, 'next', code, idx))
            
            return CFG, [current_node]
        
        return [], entry_nodes
    
    # 处理自增/自减语句
    elif root_node.type in increment_statement:
        CFG = []
        if (root_node.start_point, root_node.end_point) in point2code:
            idx, code = point2code[(root_node.start_point, root_node.end_point)]
            current_node = (code, idx)
            
            for entry_code, entry_idx in entry_nodes:
                CFG.append((entry_code, entry_idx, 'next', code, idx))
            
            return CFG, [current_node]
        return [], entry_nodes
    
    # 处理if语句
    elif root_node.type in if_statement:
        CFG = []
        
        # 找到条件、then分支和else分支
        condition = None
        then_stmt = None
        else_stmt = None
        
        for child in root_node.children:
            if child.type == 'condition' or (condition is None and 'expression' in child.type):
                condition = child
            elif child.type == 'consequence' or (then_stmt is None and condition is not None):
                if child.type != 'else' and 'else' not in str(child):
                    then_stmt = child
            elif child.type == 'alternative' or 'else' in str(child.type):
                else_stmt = child
        
        # 创建条件节点
        condition_node = None
        if condition and (condition.start_point, condition.end_point) in point2code:
            idx, code = point2code[(condition.start_point, condition.end_point)]
            condition_node = (code, idx)
            
            # 从入口连接到条件
            for entry_code, entry_idx in entry_nodes:
                CFG.append((entry_code, entry_idx, 'next', code, idx))
        
        exit_nodes = []
        
        # 处理then分支
        if then_stmt and condition_node:
            then_cfg, then_exits = CFG_java(then_stmt, point2code, [condition_node])
            CFG.extend(then_cfg)
            
            # 添加条件到then分支的true边
            if then_exits:
                cond_code, cond_idx = condition_node
                for then_code, then_idx in then_exits[:1]:  # 只连接第一个then节点
                    CFG.append((cond_code, cond_idx, 'true', then_code, then_idx))
            exit_nodes.extend(then_exits)
        
        # 处理else分支
        if else_stmt and condition_node:
            else_cfg, else_exits = CFG_java(else_stmt, point2code, [condition_node])
            CFG.extend(else_cfg)
            
            # 添加条件到else分支的false边
            if else_exits:
                cond_code, cond_idx = condition_node
                for else_code, else_idx in else_exits[:1]:  # 只连接第一个else节点
                    CFG.append((cond_code, cond_idx, 'false', else_code, else_idx))
            exit_nodes.extend(else_exits)
        else:
            # 没有else分支，条件节点本身也是出口
            if condition_node:
                exit_nodes.append(condition_node)
        
        return CFG, exit_nodes
    
    # 处理for循环
    elif root_node.type in for_statement:
        CFG = []
        
        # 找到循环的各个部分
        init_stmt = None
        condition = None
        update_stmt = None
        body = None
        
        for child in root_node.children:
            if child.type == 'init' or (init_stmt is None and 'declaration' in child.type):
                init_stmt = child
            elif child.type == 'condition' or (condition is None and 'expression' in child.type and init_stmt is not None):
                condition = child
            elif child.type == 'update' or 'update' in child.type:
                update_stmt = child
            elif child.type in block_statement or 'statement' in child.type:
                body = child
        
        current_entries = entry_nodes
        
        # 处理初始化
        if init_stmt:
            init_cfg, init_exits = CFG_java(init_stmt, point2code, current_entries)
            CFG.extend(init_cfg)
            current_entries = init_exits
        
        # 创建条件节点
        condition_node = None
        if condition and (condition.start_point, condition.end_point) in point2code:
            idx, code = point2code[(condition.start_point, condition.end_point)]
            condition_node = (code, idx)
            
            # 从初始化连接到条件
            for entry_code, entry_idx in current_entries:
                CFG.append((entry_code, entry_idx, 'next', code, idx))
        
        body_exits = []
        # 处理循环体
        if body and condition_node:
            body_cfg, body_exits = CFG_java(body, point2code, [condition_node])
            CFG.extend(body_cfg)
            
            # 条件为真进入循环体
            if body_exits:
                cond_code, cond_idx = condition_node
                for body_code, body_idx in body_exits[:1]:
                    CFG.append((cond_code, cond_idx, 'true', body_code, body_idx))
        
        # 处理更新语句
        if update_stmt and body_exits:
            update_cfg, update_exits = CFG_java(update_stmt, point2code, body_exits)
            CFG.extend(update_cfg)
            
            # 从更新语句回到条件
            if condition_node and update_exits:
                cond_code, cond_idx = condition_node
                for update_code, update_idx in update_exits:
                    CFG.append((update_code, update_idx, 'loop_back', cond_code, cond_idx))
        elif body_exits and condition_node:
            # 没有更新语句，直接从循环体回到条件
            cond_code, cond_idx = condition_node
            for body_code, body_idx in body_exits:
                CFG.append((body_code, body_idx, 'loop_back', cond_code, cond_idx))
        
        # 循环出口（条件为假）
        exit_nodes = [condition_node] if condition_node else current_entries
        return CFG, exit_nodes
    
    # 处理while循环
    elif root_node.type in while_statement:
        CFG = []
        
        # 找到条件和循环体
        condition = None
        body = None
        
        for child in root_node.children:
            if child.type == 'condition' or (condition is None and 'expression' in child.type):
                condition = child
            elif child.type in block_statement or 'statement' in child.type:
                body = child
        
        # 创建条件节点
        condition_node = None
        if condition and (condition.start_point, condition.end_point) in point2code:
            idx, code = point2code[(condition.start_point, condition.end_point)]
            condition_node = (code, idx)
            
            # 从入口连接到条件
            for entry_code, entry_idx in entry_nodes:
                CFG.append((entry_code, entry_idx, 'next', code, idx))
        
        # 处理循环体
        if body and condition_node:
            body_cfg, body_exits = CFG_java(body, point2code, [condition_node])
            CFG.extend(body_cfg)
            
            # 条件为真进入循环体
            if body_exits:
                cond_code, cond_idx = condition_node
                for body_code, body_idx in body_exits[:1]:
                    CFG.append((cond_code, cond_idx, 'true', body_code, body_idx))
                
                # 从循环体回到条件
                for body_code, body_idx in body_exits:
                    CFG.append((body_code, body_idx, 'loop_back', cond_code, cond_idx))
        
        # 循环出口（条件为假）
        exit_nodes = [condition_node] if condition_node else entry_nodes
        return CFG, exit_nodes
    
    # 处理break语句
    elif root_node.type in break_statement:
        CFG = []
        if (root_node.start_point, root_node.end_point) in point2code:
            idx, code = point2code[(root_node.start_point, root_node.end_point)]
            current_node = (code, idx)
            
            for entry_code, entry_idx in entry_nodes:
                CFG.append((entry_code, entry_idx, 'next', code, idx))
            
            # break语句没有正常的出口，它跳出循环
            return CFG, []
        return [], []
    
    # 处理continue语句
    elif root_node.type in continue_statement:
        CFG = []
        if (root_node.start_point, root_node.end_point) in point2code:
            idx, code = point2code[(root_node.start_point, root_node.end_point)]
            current_node = (code, idx)
            
            for entry_code, entry_idx in entry_nodes:
                CFG.append((entry_code, entry_idx, 'next', code, idx))
            
            # continue语句没有正常的出口，它跳到循环开始
            return CFG, []
        return [], []
    
    # 处理return语句
    elif root_node.type in return_statement:
        CFG = []
        current_nodes = entry_nodes
        
        # 先处理return的表达式
        for child in root_node.children:
            if child.type != 'return' and 'expression' in child.type:
                expr_cfg, expr_exits = CFG_java(child, point2code, current_nodes)
                CFG.extend(expr_cfg)
                current_nodes = expr_exits
        
        # 处理return语句本身
        if (root_node.start_point, root_node.end_point) in point2code:
            idx, code = point2code[(root_node.start_point, root_node.end_point)]
            current_node = (code, idx)
            
            for entry_code, entry_idx in current_nodes:
                CFG.append((entry_code, entry_idx, 'next', code, idx))
            
            # return语句没有出口，它终止函数执行
            return CFG, []
        return CFG, []
    
    # 处理代码块和其他复合语句
    else:
        CFG = []
        current_entries = entry_nodes
        
        # 顺序处理所有子节点
        for child in root_node.children:
            if child.type != 'line_comment':  # 跳过注释
                child_cfg, child_exits = CFG_java(child, point2code, current_entries)
                CFG.extend(child_cfg)
                current_entries = child_exits if child_exits else current_entries
        
        return CFG, current_entries
    
    
def CFG_python(root_node, point2code, entry_nodes=None):
    """
    为Python代码生成控制流图
    返回格式: (CFG, exit_nodes)
    CFG: 控制流边的列表，格式为 (from_code, from_idx, edge_type, to_code, to_idx)
    exit_nodes: 当前代码块的出口节点列表 [(code, idx), ...]
    entry_nodes: 当前代码块的入口节点列表 [(code, idx), ...]
    """
    # Python语法树节点类型定义
    assignment = ['assignment', 'augmented_assignment', 'for_in_clause']
    def_statement = ['default_parameter']
    increment_statement = ['update_expression']  # Python中较少使用
    if_statement = ['if_statement']
    for_statement = ['for_statement']
    while_statement = ['while_statement']
    break_statement = ['break_statement']
    continue_statement = ['continue_statement']
    return_statement = ['return_statement']
    expression_statement = ['expression_statement']
    block_statement = ['block', 'module']
    
    if entry_nodes is None:
        entry_nodes = []
    
    # 处理叶节点或简单语句
    if (len(root_node.children) == 0 or root_node.type == 'string') and root_node.type != 'comment':
        if (root_node.start_point, root_node.end_point) in point2code:
            idx, code = point2code[(root_node.start_point, root_node.end_point)]
            current_node = (code, idx)
            
            # 创建从入口节点到当前节点的边
            CFG = []
            for entry_code, entry_idx in entry_nodes:
                CFG.append((entry_code, entry_idx, 'next', code, idx))
            
            return CFG, [current_node]
        else:
            return [], entry_nodes
    
    # 处理默认参数定义语句
    elif root_node.type in def_statement:
        CFG = []
        current_nodes = []
        
        # 获取默认参数语句的位置
        if (root_node.start_point, root_node.end_point) in point2code:
            idx, code = point2code[(root_node.start_point, root_node.end_point)]
            current_node = (code, idx)
            current_nodes = [current_node]
            
            # 从入口连接到当前语句
            for entry_code, entry_idx in entry_nodes:
                CFG.append((entry_code, entry_idx, 'next', code, idx))
        
        # 处理默认值表达式
        value = root_node.child_by_field_name('value')
        if value is not None:
            value_cfg, value_exits = CFG_python(value, point2code, current_nodes)
            CFG.extend(value_cfg)
            current_nodes = value_exits
        
        return CFG, current_nodes if current_nodes else entry_nodes
    
    # 处理赋值语句（包括for_in_clause）
    elif root_node.type in assignment:
        CFG = []
        
        # 获取赋值语句的位置
        if (root_node.start_point, root_node.end_point) in point2code:
            idx, code = point2code[(root_node.start_point, root_node.end_point)]
            current_node = (code, idx)
            
            # 从入口连接到赋值语句
            for entry_code, entry_idx in entry_nodes:
                CFG.append((entry_code, entry_idx, 'next', code, idx))
            
            return CFG, [current_node]
        
        return [], entry_nodes
    
    # 处理自增/自减语句
    elif root_node.type in increment_statement:
        CFG = []
        if (root_node.start_point, root_node.end_point) in point2code:
            idx, code = point2code[(root_node.start_point, root_node.end_point)]
            current_node = (code, idx)
            
            for entry_code, entry_idx in entry_nodes:
                CFG.append((entry_code, entry_idx, 'next', code, idx))
            
            return CFG, [current_node]
        return [], entry_nodes
    
    # 处理if语句
    elif root_node.type in if_statement:
        CFG = []
        
        # 找到条件、then分支和else相关分支
        condition = None
        then_stmt = None
        else_clauses = []
        
        for child in root_node.children:
            if condition is None and 'expression' in child.type:
                condition = child
            elif child.type == 'block' and then_stmt is None:
                then_stmt = child
            elif child.type in ['elif_clause', 'else_clause']:
                else_clauses.append(child)
        
        # 创建条件节点
        condition_node = None
        if condition and (condition.start_point, condition.end_point) in point2code:
            idx, code = point2code[(condition.start_point, condition.end_point)]
            condition_node = (code, idx)
            
            # 从入口连接到条件
            for entry_code, entry_idx in entry_nodes:
                CFG.append((entry_code, entry_idx, 'next', code, idx))
        
        exit_nodes = []
        
        # 处理then分支
        if then_stmt and condition_node:
            then_cfg, then_exits = CFG_python(then_stmt, point2code, [condition_node])
            CFG.extend(then_cfg)
            
            # 添加条件到then分支的true边
            if then_exits:
                cond_code, cond_idx = condition_node
                for then_code, then_idx in then_exits[:1]:  # 只连接第一个then节点
                    CFG.append((cond_code, cond_idx, 'true', then_code, then_idx))
            exit_nodes.extend(then_exits)
        
        # 处理elif和else子句
        has_else = False
        for else_clause in else_clauses:
            if 'else' in else_clause.type:
                has_else = True
            
            if condition_node:
                else_cfg, else_exits = CFG_python(else_clause, point2code, [condition_node])
                CFG.extend(else_cfg)
                
                # 添加条件到else分支的false边
                if else_exits:
                    cond_code, cond_idx = condition_node
                    for else_code, else_idx in else_exits[:1]:  # 只连接第一个else节点
                        CFG.append((cond_code, cond_idx, 'false', else_code, else_idx))
                exit_nodes.extend(else_exits)
        
        # 如果没有else分支，条件节点本身也是出口
        if not has_else and condition_node:
            exit_nodes.append(condition_node)
        
        return CFG, exit_nodes
    
    # 处理for循环
    elif root_node.type in for_statement:
        CFG = []
        
        # 找到循环的各个部分
        left_node = root_node.child_by_field_name('left')
        right_node = root_node.child_by_field_name('right')
        body = None
        
        for child in root_node.children:
            if child.type == 'block':
                body = child
                break
        
        current_entries = entry_nodes
        
        # 处理右侧可迭代对象（相当于初始化）
        if right_node:
            init_cfg, init_exits = CFG_python(right_node, point2code, current_entries)
            CFG.extend(init_cfg)
            current_entries = init_exits
        
        # 创建条件节点（迭代器检查）
        condition_node = None
        if right_node and (right_node.start_point, right_node.end_point) in point2code:
            idx, code = point2code[(right_node.start_point, right_node.end_point)]
            condition_node = (code, idx)
            
            # 从初始化连接到条件（如果没有初始化，从入口连接）
            for entry_code, entry_idx in current_entries:
                CFG.append((entry_code, entry_idx, 'next', code, idx))
        
        body_exits = []
        # 处理循环体
        if body and condition_node:
            body_cfg, body_exits = CFG_python(body, point2code, [condition_node])
            CFG.extend(body_cfg)
            
            # 条件为真进入循环体
            if body_exits:
                cond_code, cond_idx = condition_node
                for body_code, body_idx in body_exits[:1]:
                    CFG.append((cond_code, cond_idx, 'true', body_code, body_idx))
                
                # 从循环体回到条件
                for body_code, body_idx in body_exits:
                    CFG.append((body_code, body_idx, 'loop_back', cond_code, cond_idx))
        
        # 循环出口（迭代结束）
        exit_nodes = [condition_node] if condition_node else current_entries
        return CFG, exit_nodes
    
    # 处理while循环
    elif root_node.type in while_statement:
        CFG = []
        
        # 找到条件和循环体
        condition = None
        body = None
        
        for child in root_node.children:
            if condition is None and 'expression' in child.type:
                condition = child
            elif child.type == 'block':
                body = child
        
        # 创建条件节点
        condition_node = None
        if condition and (condition.start_point, condition.end_point) in point2code:
            idx, code = point2code[(condition.start_point, condition.end_point)]
            condition_node = (code, idx)
            
            # 从入口连接到条件
            for entry_code, entry_idx in entry_nodes:
                CFG.append((entry_code, entry_idx, 'next', code, idx))
        
        # 处理循环体
        if body and condition_node:
            body_cfg, body_exits = CFG_python(body, point2code, [condition_node])
            CFG.extend(body_cfg)
            
            # 条件为真进入循环体
            if body_exits:
                cond_code, cond_idx = condition_node
                for body_code, body_idx in body_exits[:1]:
                    CFG.append((cond_code, cond_idx, 'true', body_code, body_idx))
                
                # 从循环体回到条件
                for body_code, body_idx in body_exits:
                    CFG.append((body_code, body_idx, 'loop_back', cond_code, cond_idx))
        
        # 循环出口（条件为假）
        exit_nodes = [condition_node] if condition_node else entry_nodes
        return CFG, exit_nodes
    
    # 处理break语句
    elif root_node.type in break_statement:
        CFG = []
        if (root_node.start_point, root_node.end_point) in point2code:
            idx, code = point2code[(root_node.start_point, root_node.end_point)]
            current_node = (code, idx)
            
            for entry_code, entry_idx in entry_nodes:
                CFG.append((entry_code, entry_idx, 'next', code, idx))
            
            # break语句没有正常的出口，它跳出循环
            return CFG, []
        return [], []
    
    # 处理continue语句
    elif root_node.type in continue_statement:
        CFG = []
        if (root_node.start_point, root_node.end_point) in point2code:
            idx, code = point2code[(root_node.start_point, root_node.end_point)]
            current_node = (code, idx)
            
            for entry_code, entry_idx in entry_nodes:
                CFG.append((entry_code, entry_idx, 'next', code, idx))
            
            # continue语句没有正常的出口，它跳到循环开始
            return CFG, []
        return [], []
    
    # 处理return语句
    elif root_node.type in return_statement:
        CFG = []
        current_nodes = entry_nodes
        
        # 先处理return的表达式
        for child in root_node.children:
            if child.type != 'return' and 'expression' in child.type:
                expr_cfg, expr_exits = CFG_python(child, point2code, current_nodes)
                CFG.extend(expr_cfg)
                current_nodes = expr_exits
        
        # 处理return语句本身
        if (root_node.start_point, root_node.end_point) in point2code:
            idx, code = point2code[(root_node.start_point, root_node.end_point)]
            current_node = (code, idx)
            
            for entry_code, entry_idx in current_nodes:
                CFG.append((entry_code, entry_idx, 'next', code, idx))
            
            # return语句没有出口，它终止函数执行
            return CFG, []
        return CFG, []
    
    # 处理代码块和其他复合语句
    else:
        CFG = []
        current_entries = entry_nodes
        
        # 按照DFG代码的逻辑，先处理do_first_statement类型的子节点
        do_first_statement = ['for_in_clause']
        
        # 先处理for_in_clause等需要优先处理的语句
        for child in root_node.children:
            if child.type in do_first_statement:
                child_cfg, child_exits = CFG_python(child, point2code, current_entries)
                CFG.extend(child_cfg)
                current_entries = child_exits if child_exits else current_entries
        
        # 再处理其他子节点
        for child in root_node.children:
            if child.type not in do_first_statement and child.type != 'comment':  # 跳过注释
                child_cfg, child_exits = CFG_python(child, point2code, current_entries)
                CFG.extend(child_cfg)
                current_entries = child_exits if child_exits else current_entries
        
        return CFG, current_entries



def DFG_csharp(root_node,point2code,states):
    assignment=['assignment_expression']
    def_statement=['variable_declarator']
    increment_statement=['postfix_unary_expression']
    if_statement=['if_statement','else']
    for_statement=['for_statement']
    enhanced_for_statement=['for_each_statement']
    while_statement=['while_statement']
    do_first_statement=[]
    states=states.copy()
    if (len(root_node.children)==0 or root_node.type=='string') and root_node.type!='comment':
        idx,code=point2code[(root_node.start_point,root_node.end_point)]
        if root_node.type==code:
            return [],states
        elif code in states:
            return [(code,idx,'comesFrom',[code],states[code].copy())],states
        else:
            if root_node.type=='identifier':
                states[code]=[idx]
            return [(code,idx,'comesFrom',[],[])],states
    elif root_node.type in def_statement:
        if len(root_node.children)==2:
            name=root_node.children[0]
            value=root_node.children[1]
        else:
            name=root_node.children[0]
            value=None
        DFG=[]
        if value is None:
            indexs=tree_to_variable_index(name,point2code)
            for index in indexs:
                idx,code=point2code[index]
                DFG.append((code,idx,'comesFrom',[],[]))
                states[code]=[idx]
            return sorted(DFG,key=lambda x:x[1]),states
        else:
            name_indexs=tree_to_variable_index(name,point2code)
            value_indexs=tree_to_variable_index(value,point2code)
            temp,states=DFG_csharp(value,point2code,states)
            DFG+=temp
            for index1 in name_indexs:
                idx1,code1=point2code[index1]
                for index2 in value_indexs:
                    idx2,code2=point2code[index2]
                    DFG.append((code1,idx1,'comesFrom',[code2],[idx2]))
                states[code1]=[idx1]
            return sorted(DFG,key=lambda x:x[1]),states
    elif root_node.type in assignment:
        left_nodes=root_node.child_by_field_name('left')
        right_nodes=root_node.child_by_field_name('right')
        DFG=[]
        temp,states=DFG_csharp(right_nodes,point2code,states)
        DFG+=temp
        name_indexs=tree_to_variable_index(left_nodes,point2code)
        value_indexs=tree_to_variable_index(right_nodes,point2code)
        for index1 in name_indexs:
            idx1,code1=point2code[index1]
            for index2 in value_indexs:
                idx2,code2=point2code[index2]
                DFG.append((code1,idx1,'computedFrom',[code2],[idx2]))
            states[code1]=[idx1]
        return sorted(DFG,key=lambda x:x[1]),states
    elif root_node.type in increment_statement:
        DFG=[]
        indexs=tree_to_variable_index(root_node,point2code)
        for index1 in indexs:
            idx1,code1=point2code[index1]
            for index2 in indexs:
                idx2,code2=point2code[index2]
                DFG.append((code1,idx1,'computedFrom',[code2],[idx2]))
            states[code1]=[idx1]
        return sorted(DFG,key=lambda x:x[1]),states
    elif root_node.type in if_statement:
        DFG=[]
        current_states=states.copy()
        others_states=[]
        flag=False
        tag=False
        if 'else' in root_node.type:
            tag=True
        for child in root_node.children:
            if 'else' in child.type:
                tag=True
            if child.type not in if_statement and flag is False:
                temp,current_states=DFG_csharp(child,point2code,current_states)
                DFG+=temp
            else:
                flag=True
                temp,new_states=DFG_csharp(child,point2code,states)
                DFG+=temp
                others_states.append(new_states)
        others_states.append(current_states)
        if tag is False:
            others_states.append(states)
        new_states={}
        for dic in others_states:
            for key in dic:
                if key not in new_states:
                    new_states[key]=dic[key].copy()
                else:
                    new_states[key]+=dic[key]
        for key in new_states:
            new_states[key]=sorted(list(set(new_states[key])))
        return sorted(DFG,key=lambda x:x[1]),new_states
    elif root_node.type in for_statement:
        DFG=[]
        for child in root_node.children:
            temp,states=DFG_csharp(child,point2code,states)
            DFG+=temp
        flag=False
        for child in root_node.children:
            if flag:
                temp,states=DFG_csharp(child,point2code,states)
                DFG+=temp
            elif child.type=="local_variable_declaration":
                flag=True
        dic={}
        for x in DFG:
            if (x[0],x[1],x[2]) not in dic:
                dic[(x[0],x[1],x[2])]=[x[3],x[4]]
            else:
                dic[(x[0],x[1],x[2])][0]=list(set(dic[(x[0],x[1],x[2])][0]+x[3]))
                dic[(x[0],x[1],x[2])][1]=sorted(list(set(dic[(x[0],x[1],x[2])][1]+x[4])))
        DFG=[(x[0],x[1],x[2],y[0],y[1]) for x,y in sorted(dic.items(),key=lambda t:t[0][1])]
        return sorted(DFG,key=lambda x:x[1]),states
    elif root_node.type in enhanced_for_statement:
        name=root_node.child_by_field_name('left')
        value=root_node.child_by_field_name('right')
        body=root_node.child_by_field_name('body')
        DFG=[]
        for i in range(2):
            temp,states=DFG_csharp(value,point2code,states)
            DFG+=temp
            name_indexs=tree_to_variable_index(name,point2code)
            value_indexs=tree_to_variable_index(value,point2code)
            for index1 in name_indexs:
                idx1,code1=point2code[index1]
                for index2 in value_indexs:
                    idx2,code2=point2code[index2]
                    DFG.append((code1,idx1,'computedFrom',[code2],[idx2]))
                states[code1]=[idx1]
            temp,states=DFG_csharp(body,point2code,states)
            DFG+=temp
        dic={}
        for x in DFG:
            if (x[0],x[1],x[2]) not in dic:
                dic[(x[0],x[1],x[2])]=[x[3],x[4]]
            else:
                dic[(x[0],x[1],x[2])][0]=list(set(dic[(x[0],x[1],x[2])][0]+x[3]))
                dic[(x[0],x[1],x[2])][1]=sorted(list(set(dic[(x[0],x[1],x[2])][1]+x[4])))
        DFG=[(x[0],x[1],x[2],y[0],y[1]) for x,y in sorted(dic.items(),key=lambda t:t[0][1])]
        return sorted(DFG,key=lambda x:x[1]),states
    elif root_node.type in while_statement:
        DFG=[]
        for i in range(2):
            for child in root_node.children:
                temp,states=DFG_csharp(child,point2code,states)
                DFG+=temp
        dic={}
        for x in DFG:
            if (x[0],x[1],x[2]) not in dic:
                dic[(x[0],x[1],x[2])]=[x[3],x[4]]
            else:
                dic[(x[0],x[1],x[2])][0]=list(set(dic[(x[0],x[1],x[2])][0]+x[3]))
                dic[(x[0],x[1],x[2])][1]=sorted(list(set(dic[(x[0],x[1],x[2])][1]+x[4])))
        DFG=[(x[0],x[1],x[2],y[0],y[1]) for x,y in sorted(dic.items(),key=lambda t:t[0][1])]
        return sorted(DFG,key=lambda x:x[1]),states
    else:
        DFG=[]
        for child in root_node.children:
            if child.type in do_first_statement:
                temp,states=DFG_csharp(child,point2code,states)
                DFG+=temp
        for child in root_node.children:
            if child.type not in do_first_statement:
                temp,states=DFG_csharp(child,point2code,states)
                DFG+=temp

        return sorted(DFG,key=lambda x:x[1]),states

def DFG_ruby(root_node,point2code,states):
    assignment=['assignment','operator_assignment']
    if_statement=['if','elsif','else','unless','when']
    for_statement=['for']
    while_statement=['while_modifier','until']
    do_first_statement=[]
    def_statement=['keyword_parameter']
    if (len(root_node.children)==0 or root_node.type=='string') and root_node.type!='comment':
        states=states.copy()
        idx,code=point2code[(root_node.start_point,root_node.end_point)]
        if root_node.type==code:
            return [],states
        elif code in states:
            return [(code,idx,'comesFrom',[code],states[code].copy())],states
        else:
            if root_node.type=='identifier':
                states[code]=[idx]
            return [(code,idx,'comesFrom',[],[])],states
    elif root_node.type in def_statement:
        name=root_node.child_by_field_name('name')
        value=root_node.child_by_field_name('value')
        DFG=[]
        if value is None:
            indexs=tree_to_variable_index(name,point2code)
            for index in indexs:
                idx,code=point2code[index]
                DFG.append((code,idx,'comesFrom',[],[]))
                states[code]=[idx]
            return sorted(DFG,key=lambda x:x[1]),states
        else:
            name_indexs=tree_to_variable_index(name,point2code)
            value_indexs=tree_to_variable_index(value,point2code)
            temp,states=DFG_ruby(value,point2code,states)
            DFG+=temp
            for index1 in name_indexs:
                idx1,code1=point2code[index1]
                for index2 in value_indexs:
                    idx2,code2=point2code[index2]
                    DFG.append((code1,idx1,'comesFrom',[code2],[idx2]))
                states[code1]=[idx1]
            return sorted(DFG,key=lambda x:x[1]),states
    elif root_node.type in assignment:
        left_nodes=[x for x in root_node.child_by_field_name('left').children if x.type!=',']
        right_nodes=[x for x in root_node.child_by_field_name('right').children if x.type!=',']
        if len(right_nodes)!=len(left_nodes):
            left_nodes=[root_node.child_by_field_name('left')]
            right_nodes=[root_node.child_by_field_name('right')]
        if len(left_nodes)==0:
            left_nodes=[root_node.child_by_field_name('left')]
        if len(right_nodes)==0:
            right_nodes=[root_node.child_by_field_name('right')]
        if root_node.type=="operator_assignment":
            left_nodes=[root_node.children[0]]
            right_nodes=[root_node.children[-1]]

        DFG=[]
        for node in right_nodes:
            temp,states=DFG_ruby(node,point2code,states)
            DFG+=temp

        for left_node,right_node in zip(left_nodes,right_nodes):
            left_tokens_index=tree_to_variable_index(left_node,point2code)
            right_tokens_index=tree_to_variable_index(right_node,point2code)
            temp=[]
            for token1_index in left_tokens_index:
                idx1,code1=point2code[token1_index]
                temp.append((code1,idx1,'computedFrom',[point2code[x][1] for x in right_tokens_index],
                             [point2code[x][0] for x in right_tokens_index]))
                states[code1]=[idx1]
            DFG+=temp
        return sorted(DFG,key=lambda x:x[1]),states
    elif root_node.type in if_statement:
        DFG=[]
        current_states=states.copy()
        others_states=[]
        tag=False
        if 'else' in root_node.type:
            tag=True
        for child in root_node.children:
            if 'else' in child.type:
                tag=True
            if child.type not in if_statement:
                temp,current_states=DFG_ruby(child,point2code,current_states)
                DFG+=temp
            else:
                temp,new_states=DFG_ruby(child,point2code,states)
                DFG+=temp
                others_states.append(new_states)
        others_states.append(current_states)
        if tag is False:
            others_states.append(states)
        new_states={}
        for dic in others_states:
            for key in dic:
                if key not in new_states:
                    new_states[key]=dic[key].copy()
                else:
                    new_states[key]+=dic[key]
        for key in new_states:
            new_states[key]=sorted(list(set(new_states[key])))
        return sorted(DFG,key=lambda x:x[1]),new_states
    elif root_node.type in for_statement:
        DFG=[]
        for i in range(2):
            left_nodes=[root_node.child_by_field_name('pattern')]
            right_nodes=[root_node.child_by_field_name('value')]
            assert len(right_nodes)==len(left_nodes)
            for node in right_nodes:
                temp,states=DFG_ruby(node,point2code,states)
                DFG+=temp
            for left_node,right_node in zip(left_nodes,right_nodes):
                left_tokens_index=tree_to_variable_index(left_node,point2code)
                right_tokens_index=tree_to_variable_index(right_node,point2code)
                temp=[]
                for token1_index in left_tokens_index:
                    idx1,code1=point2code[token1_index]
                    temp.append((code1,idx1,'computedFrom',[point2code[x][1] for x in right_tokens_index],
                                 [point2code[x][0] for x in right_tokens_index]))
                    states[code1]=[idx1]
                DFG+=temp
            temp,states=DFG_ruby(root_node.child_by_field_name('body'),point2code,states)
            DFG+=temp
        dic={}
        for x in DFG:
            if (x[0],x[1],x[2]) not in dic:
                dic[(x[0],x[1],x[2])]=[x[3],x[4]]
            else:
                dic[(x[0],x[1],x[2])][0]=list(set(dic[(x[0],x[1],x[2])][0]+x[3]))
                dic[(x[0],x[1],x[2])][1]=sorted(list(set(dic[(x[0],x[1],x[2])][1]+x[4])))
        DFG=[(x[0],x[1],x[2],y[0],y[1]) for x,y in sorted(dic.items(),key=lambda t:t[0][1])]
        return sorted(DFG,key=lambda x:x[1]),states
    elif root_node.type in while_statement:
        DFG=[]
        for i in range(2):
            for child in root_node.children:
                temp,states=DFG_ruby(child,point2code,states)
                DFG+=temp
        dic={}
        for x in DFG:
            if (x[0],x[1],x[2]) not in dic:
                dic[(x[0],x[1],x[2])]=[x[3],x[4]]
            else:
                dic[(x[0],x[1],x[2])][0]=list(set(dic[(x[0],x[1],x[2])][0]+x[3]))
                dic[(x[0],x[1],x[2])][1]=sorted(list(set(dic[(x[0],x[1],x[2])][1]+x[4])))
        DFG=[(x[0],x[1],x[2],y[0],y[1]) for x,y in sorted(dic.items(),key=lambda t:t[0][1])]
        return sorted(DFG,key=lambda x:x[1]),states
    else:
        DFG=[]
        for child in root_node.children:
            if child.type in do_first_statement:
                temp,states=DFG_ruby(child,point2code,states)
                DFG+=temp
        for child in root_node.children:
            if child.type not in do_first_statement:
                temp,states=DFG_ruby(child,point2code,states)
                DFG+=temp

        return sorted(DFG,key=lambda x:x[1]),states

def DFG_go(root_node,point2code,states):
    assignment=['assignment_statement',]
    def_statement=['var_spec']
    increment_statement=['inc_statement']
    if_statement=['if_statement','else']
    for_statement=['for_statement']
    enhanced_for_statement=[]
    while_statement=[]
    do_first_statement=[]
    states=states.copy()
    if (len(root_node.children)==0 or root_node.type=='string') and root_node.type!='comment':
        idx,code=point2code[(root_node.start_point,root_node.end_point)]
        if root_node.type==code:
            return [],states
        elif code in states:
            return [(code,idx,'comesFrom',[code],states[code].copy())],states
        else:
            if root_node.type=='identifier':
                states[code]=[idx]
            return [(code,idx,'comesFrom',[],[])],states
    elif root_node.type in def_statement:
        name=root_node.child_by_field_name('name')
        value=root_node.child_by_field_name('value')
        DFG=[]
        if value is None:
            indexs=tree_to_variable_index(name,point2code)
            for index in indexs:
                idx,code=point2code[index]
                DFG.append((code,idx,'comesFrom',[],[]))
                states[code]=[idx]
            return sorted(DFG,key=lambda x:x[1]),states
        else:
            name_indexs=tree_to_variable_index(name,point2code)
            value_indexs=tree_to_variable_index(value,point2code)
            temp,states=DFG_go(value,point2code,states)
            DFG+=temp
            for index1 in name_indexs:
                idx1,code1=point2code[index1]
                for index2 in value_indexs:
                    idx2,code2=point2code[index2]
                    DFG.append((code1,idx1,'comesFrom',[code2],[idx2]))
                states[code1]=[idx1]
            return sorted(DFG,key=lambda x:x[1]),states
    elif root_node.type in assignment:
        left_nodes=root_node.child_by_field_name('left')
        right_nodes=root_node.child_by_field_name('right')
        DFG=[]
        temp,states=DFG_go(right_nodes,point2code,states)
        DFG+=temp
        name_indexs=tree_to_variable_index(left_nodes,point2code)
        value_indexs=tree_to_variable_index(right_nodes,point2code)
        for index1 in name_indexs:
            idx1,code1=point2code[index1]
            for index2 in value_indexs:
                idx2,code2=point2code[index2]
                DFG.append((code1,idx1,'computedFrom',[code2],[idx2]))
            states[code1]=[idx1]
        return sorted(DFG,key=lambda x:x[1]),states
    elif root_node.type in increment_statement:
        DFG=[]
        indexs=tree_to_variable_index(root_node,point2code)
        for index1 in indexs:
            idx1,code1=point2code[index1]
            for index2 in indexs:
                idx2,code2=point2code[index2]
                DFG.append((code1,idx1,'computedFrom',[code2],[idx2]))
            states[code1]=[idx1]
        return sorted(DFG,key=lambda x:x[1]),states
    elif root_node.type in if_statement:
        DFG=[]
        current_states=states.copy()
        others_states=[]
        flag=False
        tag=False
        if 'else' in root_node.type:
            tag=True
        for child in root_node.children:
            if 'else' in child.type:
                tag=True
            if child.type not in if_statement and flag is False:
                temp,current_states=DFG_go(child,point2code,current_states)
                DFG+=temp
            else:
                flag=True
                temp,new_states=DFG_go(child,point2code,states)
                DFG+=temp
                others_states.append(new_states)
        others_states.append(current_states)
        if tag is False:
            others_states.append(states)
        new_states={}
        for dic in others_states:
            for key in dic:
                if key not in new_states:
                    new_states[key]=dic[key].copy()
                else:
                    new_states[key]+=dic[key]
        for key in states:
            if key not in new_states:
                new_states[key]=states[key]
            else:
                new_states[key]+=states[key]
        for key in new_states:
            new_states[key]=sorted(list(set(new_states[key])))
        return sorted(DFG,key=lambda x:x[1]),new_states
    elif root_node.type in for_statement:
        DFG=[]
        for child in root_node.children:
            temp,states=DFG_go(child,point2code,states)
            DFG+=temp
        flag=False
        for child in root_node.children:
            if flag:
                temp,states=DFG_go(child,point2code,states)
                DFG+=temp
            elif child.type=="for_clause":
                if child.child_by_field_name('update') is not None:
                    temp,states=DFG_go(child.child_by_field_name('update'),point2code,states)
                    DFG+=temp
                flag=True
        dic={}
        for x in DFG:
            if (x[0],x[1],x[2]) not in dic:
                dic[(x[0],x[1],x[2])]=[x[3],x[4]]
            else:
                dic[(x[0],x[1],x[2])][0]=list(set(dic[(x[0],x[1],x[2])][0]+x[3]))
                dic[(x[0],x[1],x[2])][1]=sorted(list(set(dic[(x[0],x[1],x[2])][1]+x[4])))
        DFG=[(x[0],x[1],x[2],y[0],y[1]) for x,y in sorted(dic.items(),key=lambda t:t[0][1])]
        return sorted(DFG,key=lambda x:x[1]),states
    else:
        DFG=[]
        for child in root_node.children:
            if child.type in do_first_statement:
                temp,states=DFG_go(child,point2code,states)
                DFG+=temp
        for child in root_node.children:
            if child.type not in do_first_statement:
                temp,states=DFG_go(child,point2code,states)
                DFG+=temp

        return sorted(DFG,key=lambda x:x[1]),states

def DFG_php(root_node,point2code,states):
    assignment=['assignment_expression','augmented_assignment_expression']
    def_statement=['simple_parameter']
    increment_statement=['update_expression']
    if_statement=['if_statement','else_clause']
    for_statement=['for_statement']
    enhanced_for_statement=['foreach_statement']
    while_statement=['while_statement']
    do_first_statement=[]
    states=states.copy()
    if (len(root_node.children)==0 or root_node.type=='string') and root_node.type!='comment':
        idx,code=point2code[(root_node.start_point,root_node.end_point)]
        if root_node.type==code:
            return [],states
        elif code in states:
            return [(code,idx,'comesFrom',[code],states[code].copy())],states
        else:
            if root_node.type=='identifier':
                states[code]=[idx]
            return [(code,idx,'comesFrom',[],[])],states
    elif root_node.type in def_statement:
        name=root_node.child_by_field_name('name')
        value=root_node.child_by_field_name('default_value')
        DFG=[]
        if value is None:
            indexs=tree_to_variable_index(name,point2code)
            for index in indexs:
                idx,code=point2code[index]
                DFG.append((code,idx,'comesFrom',[],[]))
                states[code]=[idx]
            return sorted(DFG,key=lambda x:x[1]),states
        else:
            name_indexs=tree_to_variable_index(name,point2code)
            value_indexs=tree_to_variable_index(value,point2code)
            temp,states=DFG_php(value,point2code,states)
            DFG+=temp
            for index1 in name_indexs:
                idx1,code1=point2code[index1]
                for index2 in value_indexs:
                    idx2,code2=point2code[index2]
                    DFG.append((code1,idx1,'comesFrom',[code2],[idx2]))
                states[code1]=[idx1]
            return sorted(DFG,key=lambda x:x[1]),states
    elif root_node.type in assignment:
        left_nodes=root_node.child_by_field_name('left')
        right_nodes=root_node.child_by_field_name('right')
        DFG=[]
        temp,states=DFG_php(right_nodes,point2code,states)
        DFG+=temp
        name_indexs=tree_to_variable_index(left_nodes,point2code)
        value_indexs=tree_to_variable_index(right_nodes,point2code)
        for index1 in name_indexs:
            idx1,code1=point2code[index1]
            for index2 in value_indexs:
                idx2,code2=point2code[index2]
                DFG.append((code1,idx1,'computedFrom',[code2],[idx2]))
            states[code1]=[idx1]
        return sorted(DFG,key=lambda x:x[1]),states
    elif root_node.type in increment_statement:
        DFG=[]
        indexs=tree_to_variable_index(root_node,point2code)
        for index1 in indexs:
            idx1,code1=point2code[index1]
            for index2 in indexs:
                idx2,code2=point2code[index2]
                DFG.append((code1,idx1,'computedFrom',[code2],[idx2]))
            states[code1]=[idx1]
        return sorted(DFG,key=lambda x:x[1]),states
    elif root_node.type in if_statement:
        DFG=[]
        current_states=states.copy()
        others_states=[]
        flag=False
        tag=False
        if 'else' in root_node.type:
            tag=True
        for child in root_node.children:
            if 'else' in child.type:
                tag=True
            if child.type not in if_statement and flag is False:
                temp,current_states=DFG_php(child,point2code,current_states)
                DFG+=temp
            else:
                flag=True
                temp,new_states=DFG_php(child,point2code,states)
                DFG+=temp
                others_states.append(new_states)
        others_states.append(current_states)
        new_states={}
        for dic in others_states:
            for key in dic:
                if key not in new_states:
                    new_states[key]=dic[key].copy()
                else:
                    new_states[key]+=dic[key]
        for key in states:
            if key not in new_states:
                new_states[key]=states[key]
            else:
                new_states[key]+=states[key]
        for key in new_states:
            new_states[key]=sorted(list(set(new_states[key])))
        return sorted(DFG,key=lambda x:x[1]),new_states
    elif root_node.type in for_statement:
        DFG=[]
        for child in root_node.children:
            temp,states=DFG_php(child,point2code,states)
            DFG+=temp
        flag=False
        for child in root_node.children:
            if flag:
                temp,states=DFG_php(child,point2code,states)
                DFG+=temp
            elif child.type=="assignment_expression":
                flag=True
        dic={}
        for x in DFG:
            if (x[0],x[1],x[2]) not in dic:
                dic[(x[0],x[1],x[2])]=[x[3],x[4]]
            else:
                dic[(x[0],x[1],x[2])][0]=list(set(dic[(x[0],x[1],x[2])][0]+x[3]))
                dic[(x[0],x[1],x[2])][1]=sorted(list(set(dic[(x[0],x[1],x[2])][1]+x[4])))
        DFG=[(x[0],x[1],x[2],y[0],y[1]) for x,y in sorted(dic.items(),key=lambda t:t[0][1])]
        return sorted(DFG,key=lambda x:x[1]),states
    elif root_node.type in enhanced_for_statement:
        name=None
        value=None
        for child in root_node.children:
            if child.type=='variable_name' and value is None:
                value=child
            elif child.type=='variable_name' and name is None:
                name=child
                break
        body=root_node.child_by_field_name('body')
        DFG=[]
        for i in range(2):
            temp,states=DFG_php(value,point2code,states)
            DFG+=temp
            name_indexs=tree_to_variable_index(name,point2code)
            value_indexs=tree_to_variable_index(value,point2code)
            for index1 in name_indexs:
                idx1,code1=point2code[index1]
                for index2 in value_indexs:
                    idx2,code2=point2code[index2]
                    DFG.append((code1,idx1,'computedFrom',[code2],[idx2]))
                states[code1]=[idx1]
            temp,states=DFG_php(body,point2code,states)
            DFG+=temp
        dic={}
        for x in DFG:
            if (x[0],x[1],x[2]) not in dic:
                dic[(x[0],x[1],x[2])]=[x[3],x[4]]
            else:
                dic[(x[0],x[1],x[2])][0]=list(set(dic[(x[0],x[1],x[2])][0]+x[3]))
                dic[(x[0],x[1],x[2])][1]=sorted(list(set(dic[(x[0],x[1],x[2])][1]+x[4])))
        DFG=[(x[0],x[1],x[2],y[0],y[1]) for x,y in sorted(dic.items(),key=lambda t:t[0][1])]
        return sorted(DFG,key=lambda x:x[1]),states
    elif root_node.type in while_statement:
        DFG=[]
        for i in range(2):
            for child in root_node.children:
                temp,states=DFG_php(child,point2code,states)
                DFG+=temp
        dic={}
        for x in DFG:
            if (x[0],x[1],x[2]) not in dic:
                dic[(x[0],x[1],x[2])]=[x[3],x[4]]
            else:
                dic[(x[0],x[1],x[2])][0]=list(set(dic[(x[0],x[1],x[2])][0]+x[3]))
                dic[(x[0],x[1],x[2])][1]=sorted(list(set(dic[(x[0],x[1],x[2])][1]+x[4])))
        DFG=[(x[0],x[1],x[2],y[0],y[1]) for x,y in sorted(dic.items(),key=lambda t:t[0][1])]
        return sorted(DFG,key=lambda x:x[1]),states
    else:
        DFG=[]
        for child in root_node.children:
            if child.type in do_first_statement:
                temp,states=DFG_php(child,point2code,states)
                DFG+=temp
        for child in root_node.children:
            if child.type not in do_first_statement:
                temp,states=DFG_php(child,point2code,states)
                DFG+=temp

        return sorted(DFG,key=lambda x:x[1]),states

def DFG_javascript(root_node,point2code,states):
    assignment=['assignment_pattern','augmented_assignment_expression']
    def_statement=['variable_declarator']
    increment_statement=['update_expression']
    if_statement=['if_statement','else']
    for_statement=['for_statement']
    enhanced_for_statement=[]
    while_statement=['while_statement']
    do_first_statement=[]
    states=states.copy()
    if (len(root_node.children)==0 or root_node.type=='string') and root_node.type!='comment':
        idx,code=point2code[(root_node.start_point,root_node.end_point)]
        if root_node.type==code:
            return [],states
        elif code in states:
            return [(code,idx,'comesFrom',[code],states[code].copy())],states
        else:
            if root_node.type=='identifier':
                states[code]=[idx]
            return [(code,idx,'comesFrom',[],[])],states
    elif root_node.type in def_statement:
        name=root_node.child_by_field_name('name')
        value=root_node.child_by_field_name('value')
        DFG=[]
        if value is None:
            indexs=tree_to_variable_index(name,point2code)
            for index in indexs:
                idx,code=point2code[index]
                DFG.append((code,idx,'comesFrom',[],[]))
                states[code]=[idx]
            return sorted(DFG,key=lambda x:x[1]),states
        else:
            name_indexs=tree_to_variable_index(name,point2code)
            value_indexs=tree_to_variable_index(value,point2code)
            temp,states=DFG_javascript(value,point2code,states)
            DFG+=temp            
            for index1 in name_indexs:
                idx1,code1=point2code[index1]
                for index2 in value_indexs:
                    idx2,code2=point2code[index2]
                    DFG.append((code1,idx1,'comesFrom',[code2],[idx2]))
                states[code1]=[idx1]   
            return sorted(DFG,key=lambda x:x[1]),states
    elif root_node.type in assignment:
        left_nodes=root_node.child_by_field_name('left')
        right_nodes=root_node.child_by_field_name('right')
        DFG=[]
        temp,states=DFG_javascript(right_nodes,point2code,states)
        DFG+=temp            
        name_indexs=tree_to_variable_index(left_nodes,point2code)
        value_indexs=tree_to_variable_index(right_nodes,point2code)        
        for index1 in name_indexs:
            idx1,code1=point2code[index1]
            for index2 in value_indexs:
                idx2,code2=point2code[index2]
                DFG.append((code1,idx1,'computedFrom',[code2],[idx2]))
            states[code1]=[idx1]   
        return sorted(DFG,key=lambda x:x[1]),states
    elif root_node.type in increment_statement:
        DFG=[]
        indexs=tree_to_variable_index(root_node,point2code)
        for index1 in indexs:
            idx1,code1=point2code[index1]
            for index2 in indexs:
                idx2,code2=point2code[index2]
                DFG.append((code1,idx1,'computedFrom',[code2],[idx2]))
            states[code1]=[idx1]
        return sorted(DFG,key=lambda x:x[1]),states   
    elif root_node.type in if_statement:
        DFG=[]
        current_states=states.copy()
        others_states=[]
        flag=False
        tag=False
        if 'else' in root_node.type:
            tag=True
        for child in root_node.children:
            if 'else' in child.type:
                tag=True
            if child.type not in if_statement and flag is False:
                temp,current_states=DFG_javascript(child,point2code,current_states)
                DFG+=temp
            else:
                flag=True
                temp,new_states=DFG_javascript(child,point2code,states)
                DFG+=temp
                others_states.append(new_states)
        others_states.append(current_states)
        if tag is False:
            others_states.append(states)        
        new_states={}
        for dic in others_states:
            for key in dic:
                if key not in new_states:
                    new_states[key]=dic[key].copy()
                else:
                    new_states[key]+=dic[key]
        for key in states:
            if key not in new_states:
                new_states[key]=states[key]
            else:
                new_states[key]+=states[key]
        for key in new_states:
            new_states[key]=sorted(list(set(new_states[key])))
        return sorted(DFG,key=lambda x:x[1]),new_states
    elif root_node.type in for_statement:
        DFG=[]
        for child in root_node.children:
            temp,states=DFG_javascript(child,point2code,states)
            DFG+=temp
        flag=False
        for child in root_node.children:
            if flag:
                temp,states=DFG_javascript(child,point2code,states)
                DFG+=temp                
            elif child.type=="variable_declaration":               
                flag=True
        dic={}
        for x in DFG:
            if (x[0],x[1],x[2]) not in dic:
                dic[(x[0],x[1],x[2])]=[x[3],x[4]]
            else:
                dic[(x[0],x[1],x[2])][0]=list(set(dic[(x[0],x[1],x[2])][0]+x[3]))
                dic[(x[0],x[1],x[2])][1]=sorted(list(set(dic[(x[0],x[1],x[2])][1]+x[4])))
        DFG=[(x[0],x[1],x[2],y[0],y[1]) for x,y in sorted(dic.items(),key=lambda t:t[0][1])]
        return sorted(DFG,key=lambda x:x[1]),states
    elif root_node.type in while_statement:  
        DFG=[]
        for i in range(2):
            for child in root_node.children:
                temp,states=DFG_javascript(child,point2code,states)
                DFG+=temp    
        dic={}
        for x in DFG:
            if (x[0],x[1],x[2]) not in dic:
                dic[(x[0],x[1],x[2])]=[x[3],x[4]]
            else:
                dic[(x[0],x[1],x[2])][0]=list(set(dic[(x[0],x[1],x[2])][0]+x[3]))
                dic[(x[0],x[1],x[2])][1]=sorted(list(set(dic[(x[0],x[1],x[2])][1]+x[4])))
        DFG=[(x[0],x[1],x[2],y[0],y[1]) for x,y in sorted(dic.items(),key=lambda t:t[0][1])]
        return sorted(DFG,key=lambda x:x[1]),states    
    else:
        DFG=[]
        for child in root_node.children:
            if child.type in do_first_statement:
                temp,states=DFG_javascript(child,point2code,states)
                DFG+=temp
        for child in root_node.children:
            if child.type not in do_first_statement:
                temp,states=DFG_javascript(child,point2code,states)
                DFG+=temp
        
        return sorted(DFG,key=lambda x:x[1]),states


     
