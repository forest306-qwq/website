#include <stdio.h>
#include <stdbool.h>
#define MAX_NUM 100
//struct stack* s;
struct stack{
    int arr[MAX_NUM];
    int top;
};
int InitialStack(struct stack* pointer){
    pointer->top = -1;
    return pointer->top;
}

_Bool IsEmpty(struct stack* pointer){
    return pointer->top == -1;
}

_Bool IsFull(struct stack* pointer){
    return pointer->top == MAX_NUM - 1;
}

void Push(struct stack* pointer,int value){
    // if(IsFull){
    if(IsFull(pointer)){
        printf("栈已满，无法加栈\n");
        return;
    }
    pointer->arr[++pointer->top] = value;
}

void Pop(struct stack* pointer){
    // if(IsEmpty){
    if(IsEmpty(pointer)){
        printf("栈空，无法减栈\n");
        return;
    }
    pointer->arr[pointer->top--] = 0;
}

void Peak(struct stack* pointer){
    if(IsEmpty(pointer)){
        printf("栈空\n");
        return;
    }
    printf("栈顶值为:%d\n",pointer->arr[pointer->top]);
} 


int main(){
    struct stack m;
    struct stack* s = &m;

    
    InitialStack(s);
    Push(s,10);
    Push(s,20);
    Push(s,30);
    Peak(s);
    return 0;
}


