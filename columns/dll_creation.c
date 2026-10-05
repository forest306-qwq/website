#include <stdio.h>
#include <stdlib.h>
struct dllNode{
    int data;
    struct dllNode* prev;
    struct dllNode* next;
};

struct dllNode* dllCreate(int value){
    struct dllNode* NewNode = malloc(sizeof(struct dllNode));
    if(NewNode == NULL){
        printf("内存申请失败\n");
        return NULL;
    }
    NewNode->data = value;
    NewNode->next = NULL;
    NewNode->prev = NULL;
    return NewNode;
}

struct dllNode* InsertHead(struct dllNode* head,struct dllNode* NewNode){
    if(head == NULL){
        printf("原链表为空，无法头部插入\n");
        return NULL;
    }
    if(NewNode == NULL){
        printf("未接收到插入的节点指针\n");
        return NULL;
    }
    NewNode->next = head;
    head->prev = NewNode;
    head = NewNode;
    return head;
}

void InsertAfter(struct dllNode* prevNode,struct dllNode* NewNode){
    if(prevNode == NULL){
        printf("未找到前置节点指针，无法插入\n");
        return;
    }
    if(NewNode == NULL){
        printf("未接收到插入的节点指针\n");
        return;
    }
    if(prevNode -> next != NULL){
        NewNode -> next = prevNode -> next;
        prevNode -> next ->prev = NewNode;
    }
    prevNode -> next = NewNode;
    NewNode -> prev = prevNode;


    return;

}

struct dllNode* InsertTail(struct dllNode* tail,struct dllNode* NewNode){
    if(tail == NULL){
        printf("未找到前置节点指针，无法插入\n");
        return;
    }
    if(NewNode == NULL){
        printf("未接收到插入的节点指针\n");
        return;
    }
    tail -> next = NewNode;
    NewNode -> prev = tail;
    tail = NewNode;
    return tail;
}

struct dllNode* TraveserForward(struct dllNode* head){
    if(head == NULL){
        printf("链表为空\n");
        return NULL;
    }
    int count = 1;
    struct dllNode* traveser = head;
    while(traveser->next != NULL){
        traveser = traveser -> next;
        count++;
    }
    struct dllNode* tail = traveser;
    printf("一共遍历了%d个节点\n",count);
    return tail;
}

struct dllNode* TraveserBackward(struct dllNode* tail){
    if(tail == NULL){
        printf("链表为空\n");
        return NULL;
    }
    int count = 1;
    struct dllNode* traveser = tail;
    while(traveser -> prev != NULL){
        traveser = traveser -> prev;
        count++;
    }
    struct dllNode* head = traveser;
    printf("一共反向遍历了%d个节点\n",count);
    return head;
}

struct dllNode* NodeDelete(struct dllNode* head,struct dllNode* del){
    if(del == head){
        head = del->next;
    }
    if(del ->next != NULL){
        del -> next -> prev = del ->prev;
    }
    if(del ->prev != NULL){
        del ->prev ->next = del -> next;
    }

    free(del);
    return head;
}

