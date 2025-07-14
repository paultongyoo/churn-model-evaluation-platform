FROM public.ecr.aws/lambda/python:3.12

RUN pip install -U pip
RUN pip install pipenv

WORKDIR /var/task

COPY [ "Pipfile", "Pipfile.lock", "./" ]

RUN pipenv install --system --deploy

COPY lambda_function.py .

CMD ["lambda_function.lambda_handler"]
