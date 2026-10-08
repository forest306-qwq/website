#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
struct linklist{
    int data;
    struct linklist* next;
};

struct linklist* InitailStack(void){
    struct linklist* head = NULL;
    return head;
} 

struct linklist* PushStack(struct linklist* head,int value){
    struct linklist* NewNode = malloc(sizeof(struct linklist));
    NewNode -> next = head;
    NewNode -> data = value;
    head = NewNode;
    return head;
}

struct linklist* PopStack(struct linklist* head){
    if(head == NULL){
        printf("栈空，无法减栈\n");
        return NULL;
    }
    struct linklist* temp = head;
    head = head -> next;
    free(temp);
    return head;
}

void PeakStack(struct linklist* head){
    if(head == NULL){
        printf("栈空，无法打印顶栈值\n");
        return;
    }
    printf("顶栈的值为%d\n",head->data);
}

int main(){
    struct linklist* head = InitailStack();
    head = PushStack(head, 20);
    head = PushStack(head, 30);
    head = PushStack(head, 40);
    PeakStack(head);
    return 0;
    
}