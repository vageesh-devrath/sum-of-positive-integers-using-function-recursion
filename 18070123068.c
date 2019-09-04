
    #include <stdio.h>
    int f(int n);
    int main()
    {
        int num;
        printf("Enter a positive integer: ");
        scanf("%d", &num);
        printf("Sum = %d",f(num));
        return 0;
    }
    int f(int n)
    {
        if(n != 0)
            return ( n + f(n-1));
        else
            return n;
    }
  
