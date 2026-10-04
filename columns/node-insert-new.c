#include <stdio.h>
#include <stdlib.h>
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

void LinkPrint(struct Node* head){
    struct Node* traveser = head;
    int count = 0;
    if(traveser == NULL){
        printf("链表不存在\n");
        return;
    }
    while(traveser != NULL){
        printf("%d ",traveser -> data);
        traveser = traveser -> next;
        count++;
    }
    printf("一共有%d个链表\n",count);
    return;
}

int main(){
    struct Node* head = InsertHead(10,NULL);
    InsertTail(20,head);
    InsertAfter(50,head);
    LinkPrint(head);
    return 0;
}