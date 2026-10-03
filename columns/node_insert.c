#include <stdio.h>
#include <stdlib.h>
struct Node{
    int data;
    struct Node* next;
};

struct Node* Node_create(int n){
    struct Node* head = (struct Node*)malloc(sizeof(struct Node));
    head->data = 1;
    head->next = NULL;
    struct Node* tail = head;
    for(int i = 2;i <= n;i++)
    {
        struct Node* newNode = (struct Node*)malloc(sizeof(struct Node));
        newNode->data = i;
        newNode->next = NULL;
        tail->next = newNode;
        tail = newNode;
    }
    return head;
}

void Node_insert(int position,int value,struct Node* head){
    struct Node* traverse = head;
    int count = 0;
    struct Node* left_pointer = NULL;
    struct Node* right_pointer = NULL;
    

    while(traverse != NULL)
    {
        traverse = traverse->next;
        count++;
        if(count == position - 2)
        left_pointer = traverse;
        if(count == position - 1)
        right_pointer = traverse;
    }

    struct Node* newNode = (struct Node*)malloc(sizeof(struct Node));
    newNode->data = value;
    newNode->next = right_pointer;
    left_pointer->next = newNode;
}
struct Node* traverse(struct Node* head){
    printf("链表内容:");
    struct Node* traverse_pointer = head;
    while(traverse_pointer != NULL){
        printf("%d ",traverse_pointer->data);
        traverse_pointer = traverse_pointer->next;
    }
    return traverse_pointer;
} 


int main(void){
    struct Node* head = Node_create(6);
    Node_insert(4,5,head);
    traverse(head);
    return 0;
}