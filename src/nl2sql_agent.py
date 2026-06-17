from pathlib import Path
from dotenv import load_dotenv

import os

# 1. Get the directory where THIS script lives
BASE_DIR = Path(__file__).resolve().parent

# 2. Set the DB Path based on the runtime environment
if Path("/app").exists():
    # Inside Docker (Mapped via compose volumes to /app/database)
    DB_PATH = "/app/database/ecommerce.db"
else:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR.parent / "env" / ".env")
    DB_PATH = str(BASE_DIR.parent / "database" / "ecommerce.db")

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from typing import TypedDict, Literal
from pydantic import BaseModel, Field
import sqlite3
import json
import pandas as pd
from langchain.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph,START, END



llm_openai=ChatOpenAI(model= 'gpt-5.2', temperature=0)
llm_openai_mini=ChatOpenAI(model='gpt-5-mini',temperature=0)
llm_anthropic=ChatAnthropic(model='claude-sonnet-4-5-20250929',temperature=0)



class State(TypedDict):
    question:str
    is_in_scope:Literal['yes','no']
    final_answer:str

    query_generated:str
    query_result:str
    error:str
    num_of_iterations:int

    needs_graph:bool
    graph_type:str
    graph_json:str




class ScopeInspector(BaseModel):
    is_in_scope: Literal["yes", "no"] = Field(
        description=(
            "Indicates whether the user's question is relevant to the e-commerce dataset and analytics. "
            "'yes' if the question pertains to customers, orders, products, payments, reviews, sellers, or shipping data."
            "'no' if the question is unrelated, personal, political, or general knowledge."
        )
    )
    is_greeting: Literal["yes", "no"] = Field(
        description=(
            "Indicates whether the user's input is a casual greeting or introductory message."
            "'yes' for greetings"
            "'no' otherwise."
        )
    )
    reason:str=Field(description="A brief explanation describing why the question was classified as in-scope, out-of-scope, or a greeting. Should provide context for the classification in a clear and concise manner.")


def scope_inspector_node(state:State):
    print("---scope_inspector_node---")
    question=state['question']

    llm_inspector=llm_openai_mini.with_structured_output(ScopeInspector)
    system_prompt="""You are a strict guardrails system for an e-commerce database chatbot. 
    Your role is to determine whether a user's question is relevant to e-commerce data analysis, is a greeting, or is out of scope. 
    Always respond objectively based on the content of the question.
    """
    prompt="""
You are a guardrails system for an e-commerce database chatbot.

Your task is to classify the user's input into three categories:

1. Greeting:
- Casual messages such as "Hi", "Hello", "Hey", "Good morning", or "How are you?"
- If the message contains both a greeting and a valid dataset question, classify both.
2. In-Scope Question:
- Questions strictly related to the e-commerce dataset (2016–2018), including:
    customers, orders, products, sellers, payments, reviews, shipping.
- Examples:
    - "How many orders were placed last month?"
    - "Show customer distribution by state"
3. Out-of-Scope:
- Any question unrelated to the dataset, such as personal, political, general knowledge, jokes, weather, etc.

Instructions:
- Always respond objectively.
- Even if the message begins with a greeting, analyze the rest for a valid in-scope question.
- Provide a brief reason for the classification.

User Input: {question}
    """

    messages=[
        {'role':'system','content':system_prompt},
        {'role':'user','content':prompt.format(question=question)}
    ]

    response=llm_inspector.invoke(messages)

    if response.is_in_scope=='yes':
        return {'is_in_scope':response.is_in_scope}
    
    elif response.is_in_scope=='no':
        if response.is_greeting=='yes':
            greeting_message = (
                "Hello! I’m your e-commerce analytics assistant. "
                "I’m here to help you explore and analyze data from 2016 to 2018, including orders, customers, products, sellers, payments, reviews, and shipping performance."
                "How can I assist you today?"
            )
            return {'final_answer':greeting_message, 'is_in_scope': response.is_in_scope}
        elif response.is_greeting=='no':
            answer = (
                "Thanks for your question! \n\n"
                "It looks like this request is outside the scope of what I can help with. "
                "I’m here to assist with questions related to the e-commerce dataset, including:\n"
                "- Customers and their locations\n"
                "- Orders and order status (2016–2018)\n"
                "- Products and categories\n"
                "- Sellers and performance\n"
                "- Payments and transactions\n"
                "- Reviews and ratings\n"
                "- Shipping and delivery details\n\n"
                "Feel free to ask anything related to these topics, and I’ll be happy to help!"
            )
            return {'final_answer':answer, 'is_in_scope': response.is_in_scope}


def inspector_scope_route_decision_conditional_edge(state:State) ->Literal['in_scope', 'out_of_scope']:
    if state['is_in_scope']=='yes':
        print('    ---is_in_scope---')
        return 'in_scope'
    print('    ---out_of_scope---')
    return 'out_of_scope'




DB_SCHEMA= """
Database Schema for E-commerce System:

1. customers
    - customer_id (TEXT): Unique customer identifier
    - customer_unique_id (TEXT): Unique cusitmer identifier across the datasets
    - customer_zip_code_prefix (INTEGER): Customer ZIP code
    - customer_city (TEXT): Customer city
    - customer_state (TEXT): Customer state

2. geolocation
    - geolocation_zip_code_prefix (INTEGER): ZIP code prefix
    - geolocation_lat (REAL): Latitude
    - geolocation_lng (REAL): Longitude
    - geolocation_city (TEXT): City name
    - geolocation_state (TEXT): STATE Code

3. products
    - product_id (TEXT): Unique product identifier
    - product_category_name (TEXT): Product category (in Portuguese)
    - product_name_lenght (REAL): Product name length
    - product_description_lenght (REAL): Product description length
    - product_photos_qty (REAL): Number of product photos
    - product_weight_g (REAL): Product weight in grams
    - product_length_cm (REAL): Product length in cm
    - product_height_cm (REAL): Product height in cm
    - product_width_cm (REAL): Product width in cm

4. sellers
    - seller_id (TEXT): Unique seller identifier
    - seller_zip_code_prefix (INTEGER): Seller zip code
    - seller_city (TEXT): Seller city
    - seller_state (TEXT): Seller state

5. orders
    - order_id (TEXT): Unique order identifier
    - customer_id (TEXT): Foreign key to customers
    - order_status (TEXT): Order status (delivered, shipped, etc.)
    - order_purchase_timestamp (TEXT): When the order was placed
    - order_approved_at (TEXT): When payment was approved
    - order_delivered_carrier_date (TEXT): When order was handed to carrier
    - order_delivered_customer_date (TEXT): When customer received the order
    - order_estimated_delivery_date (TEXT): Estimated delivery date

6. order_items
    - order_id (TEXT): Foreign key to orders
    - order_item_id (INTEGER): Item sequence number within order
    - product_id (TEXT): Foreign key to products
    - seller_id (TEXT): Foreign key to sellers
    - shipping_limit_date (TEXT): Shipping deadline
    - price (REAL): Item price
    - freight_value (REAL): Shipping cost

7. order_payments
    - order_id (TEXT): Foreign key to orders
    - payment_sequential (INTEGER): Payment sequence number
    - payment_type (TEXT): Payment method (credit_card, boleto, etc.)
    - payment_installments (INTEGER): Number of installments
    - payment_value (REAL): Payment amount

8. order_reviews
    - review_id (TEXT): Unique review identifier
    - order_id (TEXT): Foreign key to orders
    - review_score (INTEGER): Review score (1-5)
    - review_comment_title (TEXT): Review title
    - review_comment_message (TEXT): Review message
    - review_creation_date (TEXT): When review was created
    - review_answer_timestamp (TEXT): When review was answered

9. product_category_name_translation
    - product_category_name (TEXT): Category name in Portuguese
    - product_category_name_english (TEXT): Category name in English

"""


def sql_query_generator_node(state:State):
    print("---sql_query_generator_node---")
    question=state['question']
    system_prompt = """You are a senior SQL developer specializing in e-commerce databases.
Generate only valid SQLite queries.

Strict rules:
- Output only SQL statements.
- Do not include explanations, comments, or markdown formatting.
- Ensure all queries are syntactically correct for SQLite.
- Follow all instructions provided in the user prompt.
"""

    prompt="""
You are a SQL expert. Convert the following natural language question into a valid SQLite query.

Database Schema:
{DB_SCHEMA}

Question:
{question}

Generation Rules:

1. Use only the tables and columns explicitly defined in the schema above. Do not invent tables or columns.
2. Use proper JOIN clauses with correct ON conditions when querying multiple tables.
3. Return only valid SQLite SQL statements. Do not include explanations, comments, or markdown formatting.
4. If the question contains multiple sub-questions, generate separate SQL statements separated by semicolons.
5. Use aggregate functions (COUNT, SUM, AVG, MIN, MAX) when required by the question.
6. Add a LIMIT 10 clause to any query that may return multiple rows unless the user explicitly specifies a different limit.
7. Use appropriate WHERE clauses to correctly filter results.
8. Dates are stored as TEXT in ISO format (YYYY-MM-DD). Perform date comparisons accordingly.
9. Ensure all column references are properly qualified when using JOINs to avoid ambiguity.
10. Each SQL statement must be syntactically correct and executable in SQLite.
11. If multiple SQL statements are required, place each statement on its own line.

Generate the SQL query now.
"""
    messages=[
        {'role':'system', 'content':system_prompt},
        {'role':'user', 'content': prompt.format(DB_SCHEMA=DB_SCHEMA, question=question)},
    ]
    query_generated=llm_openai.invoke(messages)
    print('    ---Query Generated---')
    return {'query_generated':query_generated.content}




def query_executor_node(state:State):
    print("---query_executor_node---")
    query_generated=state['query_generated']

    # Store all query results here
    all_results = []

    try:
        con=sqlite3.connect(DB_PATH)
        cursor=con.cursor()

        #split multiple SQL queries by ';'
        sql_queries=[
            query.strip()
            for query in query_generated.strip().rstrip(';').split(';')
            if query.strip() # ignore empty queries
        ]

        #execute each query one by one
        for i, sql_query in enumerate(sql_queries):
            cursor.execute(sql_query)

            # Check if query returns rows (SELECT)
            if cursor.description is not None:
                #fetch all rows from query
                results=cursor.fetchall()
                column_names=[col[0] for col in cursor.description]
                # convert rows to list of dictionaries
                formatted_results= [dict(zip(column_names, row)) for row in results[:100]]# limit to 100 rows

                all_results.append({
                    "query_index": i + 1,
                    "sql": sql_query,
                    "rows_returned": len(formatted_results),
                    "data": formatted_results
                })
            else:
                #for Non-SELECT query (INSERT / UPDATE / DELETE queries)
                all_results.append({
                    "query_index": i + 1,
                    "sql": sql_query,
                    "rows_affected": cursor.rowcount
                })
                
        # save changes to database
        con.commit()

        # If no results, return message
        if not all_results:
            query_result="No results found."
        else:
            #convert results to JSON string
            query_result=json.dumps(all_results, indent=2)

        error=""

    except Exception as e:
        # handle any SQL or connection errors
        query_result= ""
        error = f"SQL Execution Error: {str(e)}"

    finally:
        if 'con' in locals():
            con.close()
    
    return {'query_result':query_result,'error':error}


def error_exists_conditional_edge(state:State) -> Literal['error_exists','generate_insight']:
    error = state.get("error", "").strip()

    # No error -> generate insights
    if not error:
        print('   ---generate_insight---')
        return 'generate_insight'
    #Error exists ->error handler
    print('    ---error_exists---')
    return 'error_exists'




def error_handling_node(state:State):
    print("---error_handling_node---")
    question=state['question']
    query_generated=state['query_generated']
    error= state['error']
    num_of_iterations=state.get('num_of_iterations',0) + 1

    if num_of_iterations >= 4:
        error_message = (
            f"I apologize for the inconvenience. After several attempts, "
            f"I’m unable to produce a valid SQL query. "
            f"Last error: {error}. Please review the input or try rephrasing your question."
        )
        return {'final_answer': error_message, 'num_of_iterations': num_of_iterations}
    
    system_prompt="""
You are an expert SQL developer specializing in e-commerce databases.  
Diagnose and fix SQL errors with deep knowledge of database schemas, joins, aggregations, and query optimization.  
Return only valid, executable SQLite queries.  
Do not include explanations, comments, or markdown formatting.  
Follow the database schema and question context strictly when correcting queries.
"""
    prompt="""
The following SQL query failed. Analyze the error and generate a corrected version that will execute successfully.

Database Schema:
{DB_SCHEMA}

Original Question:
{question}

Failed SQL Query:
{sql_query}

Error Message:
{error}

Guidelines for correction:
1. Correct syntax errors and invalid references.
2. Ensure all table and column names exist in the provided schema.
3. Maintain the logic and intent of the original question.
4. Use proper JOINs, WHERE clauses, and aggregate functions as needed.
5. Return only a valid SQL query that can run in SQLite.
6. Do not add explanations, comments, or any extra text.

Generate the corrected SQL query now:
    """
    user_prompt=prompt.format(DB_SCHEMA=DB_SCHEMA, question=question, sql_query=query_generated, error=error)
    messages=[
        {'role':'system', 'content':system_prompt},
        {'role':'user', 'content':user_prompt}
    ]

    fixed_query=llm_anthropic.invoke(messages)
    return {'query_generated':fixed_query.content.strip(), 'error':'', 'num_of_iterations': num_of_iterations}


def error_conditional_edge(state:State) -> Literal['execute_query', 'END']:
    if state.get('num_of_iterations')<4:
        print('    ---execute_query---')
        return 'execute_query'
    print('    ---END---')
    return 'END'




def insight_generation_node(state:State):
    print("---insight_generation_node---")
    question=state['question']
    query_generated=state['query_generated']
    query_result=state['query_result']

    system_prompt = """
You are a professional data analyst specializing in interpreting SQL query results.
Your task is to translate raw database outputs into clear, accurate, and user-friendly
natural language insights.

Focus on clarity, correctness, and relevance to the original question.
Do not mention SQL unless necessary for clarity.
Avoid technical jargon unless it improves understanding.
Present numerical results clearly and highlight key findings.
"""
    prompt = """
You are given a user's question, the SQL query used to answer it, and the resulting data output.

Original Question:
{question}

SQL Query:
{sql_query}

Query Results:
{query_result}

Instructions:
1. Provide a clear and concise answer to the original question based strictly on the query results.
2. Interpret the data and highlight meaningful insights where relevant.
3. Present numerical values clearly (use formatting, comparisons, or context when helpful).
4. If the question has multiple parts, address each part separately.
5. Use bullet points or numbered lists when presenting multiple findings.
6. Do not restate the SQL query unless it is necessary for clarity.
7. If the result set is empty, clearly state that no matching records were found.

Final Answer:
""" 
    user_prompt=prompt.format(question=question, sql_query= query_generated, query_result=query_result)
    messages=[
        {'role':'system', 'content':system_prompt},
        {'role': 'user', 'content':user_prompt}
    ]
    answer=llm_anthropic.invoke(messages)
    print("    ---Insight Generated---")
    return {'final_answer':answer.content}




class PlotGraphDecision(BaseModel):
    need_graph:bool = Field(
        description=(
            "Indicates whether a graph visualization would improve understanding of the data."
            "Set to True if the data contains trends, category comparisons, proportions, or correlations."
            "Set to False if the data is a single value, simple count, or purely textual."
        )
    )
    graph_type: Literal["bar", "line", "pie", "scatter", "none"]= Field(
        description=(
            "The type of graph that best represents the data."
            "Use 'line' for trends over time,"
            "'bar' for comparisons between categories,"
            "'pie' for proportions or percentages,"
            "'scatter' for correlations between numeric variables,"
            "or 'none' if no graph is needed."
        )
    )


def need_graph_node(state:State):
    print("---need_graph_node---")
    question=state['question']
    query_result=state['query_result']
    error=state.get('error')

    if not query_result or query_result == "No results found." or error:
        return {'needs_graph': False, 'graph_type':""}
    
    prompt=f"""
You are a data analysis assistant.

Analyze the following question and query results to determine whether a graph visualization would improve understanding.

Question:
{question}

Query Results Sample:
{query_result[:500]}...

Decision Rules:
- Trends over time → line chart
- Comparisons between categories → bar chart
- Proportions or percentages → pie chart
- Correlation between two numeric variables → scatter plot
- Single values, simple counts, or purely textual results → no graph needed

Return a structured response that matches the provided response schema.

Requirements:
- If a graph is needed, set needs_graph to true and choose the appropriate graph_type.
- If no graph is needed, set needs_graph to false and set graph_type to "none".
- Provide a brief, clear reason explaining your decision.
"""

    decision= llm_openai_mini.with_structured_output(PlotGraphDecision).invoke(prompt)

    return {'needs_graph': decision.need_graph, 'graph_type':decision.graph_type}


def should_visualize_route_conditional_edge(state:State) ->Literal['visualize','skip']:
    if state.get('needs_graph')== True:
        print('    ---visualize---')
        return 'visualize'
    else:
        print('    ---skip---')
        return 'skip'




def plotting_node(state: State):
    print("---plotting_node---")
    # 1. Extract state data
    query_result_raw = state.get("query_result")
    graph_type = state.get("graph_type")
    question = state.get("question")

    if not query_result_raw or not graph_type or graph_type == "none":
        return {"graph_json": ""}
        
    try:
        # 2. Parse the SQL execution results
        execution_data = json.loads(query_result_raw)
        if isinstance(execution_data, list) and len(execution_data) > 0:
            rows = execution_data[0].get("data", [])
        else:
            return {"graph_json": ""}

        if not rows:
            return {"graph_json": ""}

        # 3. Prepare DataFrame
        df = pd.DataFrame(rows)
        if len(df) > 20: # Keep it clean for the UI
            df = df.head(20)

        columns = df.columns.tolist()
        sample_data = df.head(5).to_dict("records")

        # 4. Prompt for Plotly code
        system_prompt = """
        You are a senior data visualization engineer. Generate ONLY executable Python Plotly code.
        STRICT RULES:
        - Use plotly.express (px) or plotly.graph_objects (go).
        - The dataframe is already available as 'df'.
        - Do NOT include markdown blocks (```python).
        - NEVER include 'fig.show()'.
        - The final figure MUST be assigned to a variable named 'fig'.
        """

        user_prompt = f"Create a {graph_type} chart for: {question}. Columns: {columns}. Data sample: {json.dumps(sample_data)}"
        
        response = llm_openai_mini.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ])
        
        # 5. Clean the code string
        plotly_code = response.content.strip().replace("```python", "").replace("```", "").strip()
        # Direct removal of show commands to prevent new tabs
        plotly_code = plotly_code.replace("fig.show()", "").replace("pio.show(fig)", "")

        # 6. Execute in a controlled environment
        import plotly.graph_objects as go
        import plotly.express as px
        import plotly.io as pio

        # Force renderers to be silent
        pio.renderers.default = None 
        
        safe_globals = {
            "__builtins__": __builtins__,
            "df": df,
            "go": go,
            "px": px,
            "pio": pio
        }

        exec(plotly_code, safe_globals)
        
        # 7. Retrieve the figure
        fig = safe_globals.get("fig")

        # Fallback: if 'fig' wasn't used, look for any Figure object in globals
        if fig is None:
            for val in safe_globals.values():
                if isinstance(val, go.Figure):
                    fig = val
                    break
        print('    ---Figure Plotted---')
        return {"graph_json": fig.to_json() if fig else ""}

    except Exception as e:
        print(f"Visualization error: {e}")
        return {"graph_json": ""}




def create_graph():
    graph_builder=StateGraph(State)

    graph_builder.add_node('scope_inspector',scope_inspector_node)
    graph_builder.add_node('sql_query_generator',sql_query_generator_node)
    graph_builder.add_node('query_executor',query_executor_node)
    graph_builder.add_node('error_handler',error_handling_node)
    graph_builder.add_node('insight_generator',insight_generation_node)
    graph_builder.add_node('need_graph_decider',need_graph_node)
    graph_builder.add_node('graph_plotter',plotting_node)

    graph_builder.add_edge(START,'scope_inspector')
    graph_builder.add_conditional_edges('scope_inspector',inspector_scope_route_decision_conditional_edge, {'in_scope':'sql_query_generator','out_of_scope':END})
    graph_builder.add_edge('sql_query_generator','query_executor')
    graph_builder.add_conditional_edges('query_executor',error_exists_conditional_edge,{'error_exists':'error_handler','generate_insight':'insight_generator'})
    graph_builder.add_conditional_edges('error_handler', error_conditional_edge, {'execute_query':'query_executor', 'END':END})
    graph_builder.add_edge('insight_generator','need_graph_decider')
    graph_builder.add_conditional_edges('need_graph_decider',should_visualize_route_conditional_edge,{'visualize':'graph_plotter','skip':END})
    graph_builder.add_edge('graph_plotter',END)

    graph_agent=graph_builder.compile()
    return graph_agent


graph=create_graph()

def process_question(question: str) -> dict:
    """
    Process a natural language question and return the final result.
    This is a simple synchronous function for notebook usage.
    
    Args:
        question: Natural language question about the e-commerce data
        
    Returns:
        dict: Final state with answer, SQL query, and graph data if applicable
    """
    initial_state = State(question=question, is_in_scope="yes", query_generated="", query_result="", error="", num_of_iterations=0, needs_graph=False, graph_type="", graph_json="",  final_answer="" )
    
    try:
        # Invoke the graph
        final_state = graph.invoke(
            initial_state,
            config={"recursion_limit": 50}
        )
        
        return final_state
        
    except Exception as e:
        return {
            "error": str(e),
            "final_answer": f"An error occurred while processing your question: {str(e)}"
        }


def test_process_question(question: str,):
    result = process_question(question)
    
    print("Final Answer:")
    print(result.get("final_answer", "No answer generated."))

    if result.get("graph_json"):
        import plotly.io as pio
        
        # This is the most compatible renderer for VS Code / Notebooks
        # It avoids the Mime/nbformat requirement by embedding an HTML frame
        pio.renderers.default = "iframe" 
        
        fig = pio.from_json(result['graph_json'])
        fig.show()
    else:
        print("\nNo graph was generated for this question.")


def get_graph_image():
    """Returns the graph visualization as PNG binary"""
    try:
        return graph.get_graph().draw_mermaid_png()
    except Exception:
        return None







































































































































































































































