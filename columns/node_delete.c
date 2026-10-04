#include <stdio.h>
#include <stdlib.h>
#define START_LINK 2
struct Node{
    int data;
    struct Node* next;
};
struct Node* InsertHead(int value,struct Node* head){
    if(head == NULL){
        printf("链表不存在，创造新链表\n");
    }
    struct Node* NewNode = malloc(sizeof(struct Node));
    NewNode -> data = value;
    NewNode -> next = head;
    head = NewNode;
    return head;
}

struct Node* InsertTail(int value,struct Node* head){
    struct Node* NewNode = malloc(sizeof(struct Node));
    NewNode -> data = value;
    NewNode -> next = NULL;
    if(head == NULL){
        printf("链表不存在，创造新链表\n");
        head = NewNode;
        return head;
    }
    struct Node* traveser = head;
    while(traveser->next != NULL){
        traveser = traveser -> next;
    }

    traveser -> next = NewNode;
    return head;
}

struct Node* InsertAfter(int value,struct Node* prev){
    if(prev == NULL){
        printf("前驱链表不能为空\n");
        return NULL;
    }
    struct Node* NewNode = malloc(sizeof(struct Node));
    NewNode -> data = value;
    NewNode -> next = NULL;
    NewNode -> next = prev -> next;
    prev -> next = NewNode;
    return NewNode;
}

struct Node* NodeHeadDelete (struct Node* head){
    if(head == NULL){
        printf("链表不存在");
        return head;
    }
    struct Node* temp = head;
    head = head -> next;
    free(temp);
    return head;
}

struct Node* NodeTargetDelete (struct Node* head,int target){
    if(head == NULL){
        printf("空链表");
    }
    else if(head->data == target ||head->next == NULL){    
        return NodeHeadDelete(head);
    }


    else{
    int count = START_LINK;
    struct Node* traveser = head;
    while(traveser->next->data != target && traveser->next->next != NULL){
        traveser = traveser->next;
        count++;
    }
    if(traveser->next->data == target){
        NodeDelete(traveser);
        printf("删除了第%d节链表\n",count);
    }
    else{
        printf("未找到对应节点\n");
    }
    return head;
    }
}

struct Node* NodeDelete(struct Node* prev){
    struct Node* temp = prev->next;
    prev->next = prev->next->next;
    free(temp);
    return NULL;
}