#include <stdio.h>
#include <stdlib.h>
#define MAX_MUN 41
struct cllNode{
    int data;
    struct cllNode* next;
};

typedef struct cllNode cll;

cll* InsertNode(cll* LeftPointer,int value){
    cll* NewNode = malloc(sizeof(cll));
    if(NewNode == NULL){
        printf("内存申请失败\n");
        return NULL;
    }
    NewNode -> data = value;
    NewNode -> next = NewNode;

    if(LeftPointer == NULL){
        printf("创建新链表\n");
        cll* StartPointer = NewNode;
        return StartPointer;
    }
    NewNode -> next = LeftPointer -> next;
    LeftPointer -> next = NewNode;
    return NewNode;
}

cll* TraverseNode(cll* StartPointer){
    if(StartPointer == NULL){
        printf("空链表，无法遍历\n");
        return NULL;
    }
    cll* traverse_pointer = StartPointer;
    int count = 0;
    do{
        printf("%d -> ",traverse_pointer->data);
        traverse_pointer = traverse_pointer -> next;
        count++;
    }while(traverse_pointer != StartPointer);
    printf("\n");
    printf("遍历了%d个节点",count);
    return traverse_pointer;
} 

cll* DeleteNode(cll* ThisNode,cll* LeftPointer){
    if(ThisNode == NULL){
        printf("不存在此节点\n");
        return NULL;
    }
    if(LeftPointer == NULL){
        printf("前驱节点指针传入错误\n");
        return NULL;
    }
    if(ThisNode == LeftPointer){
        printf("单个节点删除，现已成为空链表\n");
        free(ThisNode);
        return NULL;
    }
    LeftPointer -> next = ThisNode -> next;
    free(ThisNode);
    return LeftPointer;
}

int main(){
    cll* head =InsertNode(NULL,1);
    cll* Left =head;
    for(int i = 2;i <= 41;i++){
        Left = InsertNode(Left,i);
    }

    int count = MAX_MUN;
    while(count >= 3){
        DeleteNode(head->next->next,head->next);
        count--;
        head = head ->next->next;
    }
    TraverseNode(head);
    return 0;
}